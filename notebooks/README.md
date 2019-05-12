# Notebooks

This folder contains some examples of [Jupyter](https://jupyter.org) notebooks, showing off various features of `bankroll` or building useful functionality on top.

## Getting started

Before trying to use these notebooks, please run `script/bootstrap` from the repository root, to create a Python virtual environment and make sure that required dependencies are properly installed.

## Configuration

These notebooks will read from the same [`bankroll.ini` configuration files](../README.md#saving-configuration) as the `bankroll` command-line tool. This allows multiple users to benefit from the exact same notebook code, and keeps sensitive credentials outside of the repository.

To create your own configuration, copy [`bankroll.default.ini`](../bankroll/bankroll.default.ini) to `~/.bankroll.ini`, or leave it in your working directory as `bankroll.ini`, then edit the file to apply your desired settings.
