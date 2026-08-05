# Installation

## Requirements

- Python 3.10 or later
- numpy >= 1.24
- matplotlib >= 3.7
- Pillow >= 9.0
- psutil >= 5.9

## Install from PyPI

```bash
pip install recoverylab
```

Dependencies are installed automatically.

## Install from source

```bash
git clone https://github.com/notrabajesmas/RecoveryLab.git
cd RecoveryLab
pip install .
```

For development (includes pytest):

```bash
pip install ".[dev]"
```

## Verify installation

```bash
recoverylab --version
# v0.6.0
```

## Without installation

You can also run directly from the source directory:

```bash
cd RecoveryLab
python recoverylab.py --version
```

Note: dependencies must still be installed even when running from source.
