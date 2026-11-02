package ai.codly.core;

import android.annotation.SuppressLint;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.net.Uri;
import android.os.Bundle;
import android.os.SystemClock;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyPermanentlyInvalidatedException;
import android.security.keystore.KeyProperties;
import android.text.InputType;
import android.util.Base64;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.inputmethod.InputMethodManager;
import android.webkit.CookieManager;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import androidx.activity.OnBackPressedCallback;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.biometric.BiometricManager;
import androidx.biometric.BiometricPrompt;
import androidx.core.content.ContextCompat;

import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;

import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/**
 * C.O.R.E. console in a WebView, unlocked with the phone's fingerprint / face.
 *
 * The console passcode is typed once, encrypted with an Android Keystore key and
 * stored on the phone. Each launch, the biometric prompt releases it and the app
 * signs in with the normal passcode form, so the server needs no changes.
 *
 * Phones whose fingerprint / face counts as "strong" get a key that only works
 * after a biometric match. Phones with only "weak" face unlock still get the
 * biometric gate, but the key itself is not biometric-bound.
 */
public class MainActivity extends AppCompatActivity {

    private static final String HOST = "console.codly.ai";
    private static final String BASE = "https://" + HOST;
    private static final String KEY_ALIAS = "core_passcode_key";
    private static final long RELOCK_AFTER_MS = 2 * 60 * 1000;
    private static final int CYAN = Color.parseColor("#00D4FF");
    private static final int MUTED = Color.parseColor("#5F8AA3");
    private static final int BG = Color.parseColor("#02070D");

    // Hides controls that do nothing inside an app WebView (browser speech, blob downloads).
    private static final String INJECT_CSS =
            "(function(){var s=document.createElement('style');"
            + "s.textContent='#voiceBtn,#dlBtn{display:none!important}';"
            + "document.head.appendChild(s);})()";

    private SharedPreferences prefs;
    private WebView web;
    private View lockView;
    private TextView status;
    private EditText passInput;
    private Button unlockBtn;
    private Button saveBtn;
    private Button resetBtn;
    private boolean signingIn;
    private boolean unlocked;
    private long backgroundedAt;

    // ------------------------------------------------------------------ lifecycle

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences("core", MODE_PRIVATE);
        FrameLayout root = new FrameLayout(this);
        root.setBackgroundColor(BG);
        web = buildWebView();
        lockView = buildLockView();
        root.addView(web, new FrameLayout.LayoutParams(-1, -1));
        root.addView(lockView, new FrameLayout.LayoutParams(-1, -1));
        setContentView(root);

        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (!unlocked) {
                    finish();
                    return;
                }
                // Close the server detail panel first, like the page's own back button.
                web.evaluateJavascript(
                        "(function(){var b=document.getElementById('bay');"
                        + "if(b&&b.classList.contains('open')){document.getElementById('backBtn').click();return true}"
                        + "return false})()",
                        handled -> {
                            if (!"true".equals(handled)) finish();
                        });
            }
        });
        lock(null);
    }

    @Override
    protected void onStop() {
        super.onStop();
        backgroundedAt = SystemClock.elapsedRealtime();
    }

    @Override
    protected void onStart() {
        super.onStart();
        if (unlocked && backgroundedAt > 0 && SystemClock.elapsedRealtime() - backgroundedAt > RELOCK_AFTER_MS) {
            lock("Locked after inactivity, sir.");
        }
    }

    // ------------------------------------------------------------------ UI

    @SuppressLint("SetJavaScriptEnabled")
    private WebView buildWebView() {
        WebView w = new WebView(this);
        w.setBackgroundColor(BG);
        WebSettings s = w.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        CookieManager.getInstance().setAcceptCookie(true);
        w.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (HOST.equals(uri.getHost()) && "https".equals(uri.getScheme())) return false;
                startActivity(new Intent(Intent.ACTION_VIEW, uri));   // anything else opens in the browser
                return true;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                if (!url.startsWith(BASE)) return;
                view.evaluateJavascript(INJECT_CSS, null);
                view.evaluateJavascript("!!document.querySelector('input[name=password]')", onLoginPage -> {
                    if (!"true".equals(onLoginPage)) {
                        signingIn = false;
                        showConsole();
                    } else if (signingIn) {
                        // The saved passcode no longer works (it was changed on the server).
                        signingIn = false;
                        forgetPasscode();
                        lock("Saved passcode was rejected. Enter the current passcode, sir.");
                    } else if (unlocked) {
                        lock("Session expired. Touch the sensor to continue, sir.");   // 1-hour session ended
                    }
                });
            }
        });
        return w;
    }

    private View buildLockView() {
        LinearLayout col = new LinearLayout(this);
        col.setOrientation(LinearLayout.VERTICAL);
        col.setGravity(Gravity.CENTER);
        col.setBackgroundColor(BG);
        int pad = dp(32);
        col.setPadding(pad, pad, pad, pad);
        col.setClickable(true);

        ImageView icon = new ImageView(this);
        icon.setImageResource(R.mipmap.ic_launcher);
        col.addView(icon, new LinearLayout.LayoutParams(dp(132), dp(132)));

        TextView title = text("C.O.R.E.", 30, CYAN, true);
        title.setLetterSpacing(0.3f);
        col.addView(title, spaced(dp(18)));
        TextView sub = text("CODLY OPERATIONS & RESPONSE ENGINE", 11, MUTED, false);
        sub.setLetterSpacing(0.15f);
        col.addView(sub, spaced(dp(4)));

        status = text("", 15, Color.parseColor("#CFEFFF"), false);
        col.addView(status, spaced(dp(28)));

        passInput = new EditText(this);
        passInput.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD);
        passInput.setHint("Console passcode");
        passInput.setTextColor(Color.WHITE);
        passInput.setHintTextColor(MUTED);
        passInput.setSingleLine(true);
        col.addView(passInput, spaced(dp(16)));

        saveBtn = button("SAVE & USE FINGERPRINT / FACE", v -> enrol());
        col.addView(saveBtn, spaced(dp(12)));
        unlockBtn = button("UNLOCK", v -> unlockWithBiometric());
        col.addView(unlockBtn, spaced(dp(12)));
        resetBtn = button("FORGET SAVED PASSCODE", v -> {
            forgetPasscode();
            lock("Saved passcode removed. Enter it again to re-enable unlock.");
        });
        resetBtn.setTextColor(MUTED);
        resetBtn.setBackgroundColor(Color.TRANSPARENT);
        col.addView(resetBtn, spaced(dp(24)));
        return col;
    }

    /** Show the lock screen; prompt straight away when a passcode is already saved. */
    private void lock(String message) {
        unlocked = false;
        lockView.setVisibility(View.VISIBLE);
        boolean enrolled = prefs.contains("ct");
        passInput.setVisibility(enrolled ? View.GONE : View.VISIBLE);
        saveBtn.setVisibility(enrolled ? View.GONE : View.VISIBLE);
        unlockBtn.setVisibility(enrolled ? View.VISIBLE : View.GONE);
        resetBtn.setVisibility(enrolled ? View.VISIBLE : View.GONE);
        if (!enrolled) {
            status.setText(message != null ? message
                    : "First time on this phone. Enter the console passcode once — after that, your fingerprint or face unlocks it.");
            return;
        }
        status.setText(message != null ? message : "Touch the sensor to unlock, sir.");
        unlockWithBiometric();
    }

    private void showConsole() {
        unlocked = true;
        lockView.setVisibility(View.GONE);
        hideKeyboard();
    }

    // ------------------------------------------------------------------ biometric + keystore

    /** STRONG fingerprint/face can guard a keystore key; WEAK-only phones get a prompt-only gate. */
    private boolean strongAvailable() {
        return BiometricManager.from(this).canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG)
                == BiometricManager.BIOMETRIC_SUCCESS;
    }

    private boolean weakAvailable() {
        return BiometricManager.from(this).canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_WEAK)
                == BiometricManager.BIOMETRIC_SUCCESS;
    }

    private void enrol() {
        String pass = passInput.getText().toString();
        if (pass.isEmpty()) {
            status.setText("Enter the passcode first, sir.");
            return;
        }
        boolean strong = strongAvailable();
        if (!strong && !weakAvailable()) {
            status.setText("No fingerprint or face is set up on this phone. Add one in Settings → Security, then try again.");
            return;
        }
        try {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.ENCRYPT_MODE, freshKey(strong));
            prompt(strong, strong ? new BiometricPrompt.CryptoObject(cipher) : null, "Register fingerprint / face",
                    result -> {
                        try {
                            Cipher c = strong ? result.getCryptoObject().getCipher() : cipher;
                            byte[] ct = c.doFinal(pass.getBytes(StandardCharsets.UTF_8));
                            prefs.edit()
                                    .putString("ct", Base64.encodeToString(ct, Base64.NO_WRAP))
                                    .putString("iv", Base64.encodeToString(c.getIV(), Base64.NO_WRAP))
                                    .putBoolean("strong", strong)
                                    .apply();
                            passInput.setText("");
                            signIn(pass);
                        } catch (Exception e) {
                            status.setText("Could not save the passcode: " + e.getMessage());
                        }
                    });
        } catch (Exception e) {
            status.setText("Could not prepare secure storage: " + e.getMessage());
        }
    }

    private void unlockWithBiometric() {
        boolean strong = prefs.getBoolean("strong", true);
        try {
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            byte[] iv = Base64.decode(prefs.getString("iv", ""), Base64.NO_WRAP);
            cipher.init(Cipher.DECRYPT_MODE, existingKey(), new GCMParameterSpec(128, iv));
            prompt(strong, strong ? new BiometricPrompt.CryptoObject(cipher) : null, "Unlock C.O.R.E.",
                    result -> {
                        try {
                            Cipher c = strong ? result.getCryptoObject().getCipher() : cipher;
                            byte[] ct = Base64.decode(prefs.getString("ct", ""), Base64.NO_WRAP);
                            signIn(new String(c.doFinal(ct), StandardCharsets.UTF_8));
                        } catch (Exception e) {
                            status.setText("Unlock failed: " + e.getMessage());
                        }
                    });
        } catch (KeyPermanentlyInvalidatedException e) {
            // A fingerprint/face was added or removed on the phone: Android voids the key on purpose.
            forgetPasscode();
            lock("Your phone's fingerprints / face changed. Enter the passcode again to re-register, sir.");
        } catch (Exception e) {
            forgetPasscode();
            lock("Secure storage was reset. Enter the passcode again, sir.");
        }
    }

    private interface OnAuth {
        void run(BiometricPrompt.AuthenticationResult result);
    }

    private void prompt(boolean strong, BiometricPrompt.CryptoObject crypto, String title, OnAuth onSuccess) {
        BiometricPrompt bp = new BiometricPrompt(this, ContextCompat.getMainExecutor(this),
                new BiometricPrompt.AuthenticationCallback() {
                    @Override
                    public void onAuthenticationSucceeded(@NonNull BiometricPrompt.AuthenticationResult result) {
                        status.setText("Identity confirmed. Signing in…");
                        onSuccess.run(result);
                    }

                    @Override
                    public void onAuthenticationError(int code, @NonNull CharSequence msg) {
                        status.setText(msg + (prefs.contains("ct") ? "\nTap UNLOCK to try again." : ""));
                    }
                });
        BiometricPrompt.PromptInfo info = new BiometricPrompt.PromptInfo.Builder()
                .setTitle(title)
                .setSubtitle("Codly server console")
                .setNegativeButtonText("Cancel")
                .setAllowedAuthenticators(strong ? BiometricManager.Authenticators.BIOMETRIC_STRONG
                        : BiometricManager.Authenticators.BIOMETRIC_WEAK)
                .build();
        if (crypto != null) bp.authenticate(info, crypto);
        else bp.authenticate(info);
    }

    private SecretKey freshKey(boolean biometricBound) throws Exception {
        KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
        ks.load(null);
        ks.deleteEntry(KEY_ALIAS);
        KeyGenParameterSpec.Builder spec = new KeyGenParameterSpec.Builder(KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256);
        if (biometricBound) {
            spec.setUserAuthenticationRequired(true).setInvalidatedByBiometricEnrollment(true);
        }
        KeyGenerator gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
        gen.init(spec.build());
        return gen.generateKey();
    }

    private SecretKey existingKey() throws Exception {
        KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
        ks.load(null);
        return (SecretKey) ks.getKey(KEY_ALIAS, null);
    }

    private void forgetPasscode() {
        prefs.edit().clear().apply();
        try {
            KeyStore ks = KeyStore.getInstance("AndroidKeyStore");
            ks.load(null);
            ks.deleteEntry(KEY_ALIAS);
        } catch (Exception ignored) {
            // nothing stored
        }
    }

    // ------------------------------------------------------------------ sign-in

    /** Posts the normal passcode form; the server answers with its session cookie and the console. */
    private void signIn(String passcode) {
        try {
            signingIn = true;
            String body = "password=" + URLEncoder.encode(passcode, "UTF-8");
            web.postUrl(BASE + "/login", body.getBytes(StandardCharsets.UTF_8));
        } catch (Exception e) {
            signingIn = false;
            status.setText("Sign-in failed: " + e.getMessage());
        }
    }

    // ------------------------------------------------------------------ small helpers

    private TextView text(String s, int sp, int color, boolean bold) {
        TextView t = new TextView(this);
        t.setText(s);
        t.setTextSize(sp);
        t.setTextColor(color);
        t.setGravity(Gravity.CENTER);
        if (bold) t.setTypeface(Typeface.DEFAULT_BOLD);
        return t;
    }

    private Button button(String label, View.OnClickListener onClick) {
        Button b = new Button(this);
        b.setText(label);
        b.setTextColor(CYAN);
        b.setBackgroundColor(Color.parseColor("#1A00D4FF"));
        b.setOnClickListener(onClick);
        return b;
    }

    private LinearLayout.LayoutParams spaced(int top) {
        LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.topMargin = top;
        return lp;
    }

    private int dp(int v) {
        return Math.round(v * getResources().getDisplayMetrics().density);
    }

    private void hideKeyboard() {
        InputMethodManager imm = (InputMethodManager) getSystemService(INPUT_METHOD_SERVICE);
        if (imm != null) imm.hideSoftInputFromWindow(lockView.getWindowToken(), 0);
    }
}
