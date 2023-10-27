# Installation

## Chrophos

```bash
pip install chrophos
```


## Raspberry Pi 4

Start to finish installation of Chrophos on a Raspberry Pi 4

### Rawpy

In chrophos venv:

```sh
sudo apt install libraw-dev
pip install cython numpy wheel
```

I can't get rawpy to install directly from git, but manually building the wheel worked:
```sh
git clone https://github.com/letmaik/rawpy.git
cd rawpy
python setup.py build bdist_wheel
pip install dist/rawpy-0.18.1-cp39-cp39-linux_armv7l.whl
```
