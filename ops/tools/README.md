# Checking Pyarmour

Small local utility for checking that backend Python files stay under a size limit.

Default behavior:

- scans `Codly_Backend`
- checks backend source `.py` files only
- skips `.venv`, `dist`, and cache folders
- flags any file over `48 KB`
- exits with a non-zero status if violations are found

Run it with:

```bash
python3 "Checking Pyarmour/check_backend_python_sizes.py"
```

You can also point it at a different folder:

```bash
python3 "Checking Pyarmour/check_backend_python_sizes.py" --root /path/to/backend
```
