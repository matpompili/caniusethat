# Changelog

## [Unreleased](https://github.com/matpompili/caniusethat/tree/main)

-   Bump `pyzmq` from 23.2.1 to 24.0.1.
-   Now Windows can interrupt remote procedure calls with `Ctrl+C`. (PR #19)
-   Remote procedure calls are now thread-safe. (PR #19)

[Full Unreleased Changelog](https://github.com/matpompili/caniusethat/compare/v0.3.2...main)

## [v0.3.2](https://github.com/matpompili/caniusethat/tree/v0.3.2) (2022-09-07)

-   Fixed bug for setup.py entry point.

[Full v0.3.2 Changelog](https://github.com/matpompili/caniusethat/compare/v0.3.1...v0.3.2)

## [v0.3.1](https://github.com/matpompili/caniusethat/tree/v0.3.1) (2022-09-07)

-   Added a command line interface tool, `caniusethat-cli` useful for testing/debugging purposes.

[Full v0.3.1 Changelog](https://github.com/matpompili/caniusethat/compare/v0.3.0...v0.3.1)

## [v0.3.0](https://github.com/matpompili/caniusethat/tree/v0.3.0) (2022-09-02)

-   Fix error when docstring is not present in the function. (Issue #1, PR #4)
-   Add `pyzmq.utils.win32.allow_interrupt` to the server threads, so they can be stopped on Windows. (Issue #2, PR #6)
-   Move some of the logging to `DEBUG` level. (Issue #3, PR #7)
-   Add reserved method names to `Thing` class. (Issue #5, PR #8)

[Full v0.3.0 Changelog](https://github.com/matpompili/caniusethat/compare/v0.2.3...v0.3.0)

## [v0.2.3](https://github.com/matpompili/caniusethat/tree/v0.2.3) (2022-09-01)

-   Make `requirements.txt` less strict.

[Full v0.2.3 Changelog](https://github.com/matpompili/caniusethat/compare/v0.2.2...v0.2.3)

## [v0.2.2](https://github.com/matpompili/caniusethat/tree/v0.2.2) (2022-09-01)

-   Fix test hanging up because of logging in multiple threads

[Full v0.2.2 Changelog](https://github.com/matpompili/caniusethat/compare/v0.2.1...v0.2.2)
