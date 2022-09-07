# 👀 caniusethat

[![Documentation Status](https://readthedocs.org/projects/caniusethat/badge/?version=latest)](https://caniusethat.readthedocs.io/en/latest/?badge=latest)
[![PyPI](https://img.shields.io/pypi/v/caniusethat)](https://pypi.org/project/caniusethat/)
[![License: MIT](https://img.shields.io/badge/license-MIT-brightgreen)](https://github.com/matpompili/caniusethat/blob/main/LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests](https://github.com/matpompili/caniusethat/actions/workflows/python-package.yml/badge.svg)](https://github.com/matpompili/caniusethat/actions/workflows/python-package.yml)
[![Codacy Code Quality](https://app.codacy.com/project/badge/Grade/524f9decd5824df29734e1c9573a4af5)](https://www.codacy.com/gh/matpompili/caniusethat/dashboard?utm_source=github.com&amp;utm_medium=referral&amp;utm_content=matpompili/caniusethat&amp;utm_campaign=Badge_Grade)
[![Codacy Coverage](https://app.codacy.com/project/badge/Coverage/524f9decd5824df29734e1c9573a4af5)](https://www.codacy.com/gh/matpompili/caniusethat/dashboard?utm_source=github.com&utm_medium=referral&utm_content=matpompili/caniusethat&utm_campaign=Badge_Coverage)

`caniusethat` is a wrapper around PyZMQ that enables easy RPC (remote procedure call) functionality.

## Security warning
This module uses `pickle` to serialize and deserialize data. 
From the [Python documentation](https://docs.python.org/3/library/pickle.html):
> The `pickle` module is **not secure**. Only unpickle data you trust.
> It is possible to construct malicious pickle data which will execute arbitrary code during unpickling. Never unpickle data that could have come from an untrusted source, or that could have been tampered with.

Only use `caniusethat` on your local machine, or behind a firewall that is configured to allow connections only within your local network, or in any case from machines you trust.

## Get started

`caniusethat` can be installed via `pip`:

```bash
pip install caniusethat
```