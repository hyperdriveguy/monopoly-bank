# Monopoly E-Bank
## Overview
This is a web application designed to be used for banking with the Monopoly board game.
It allows for cashless transactions and money storage to occur.
I've been writing to learn more about web applications and see what works when complimenting a board game with additional software.

[Software Demo and Code Overview](https://youtu.be/cM9IbeM4O2Y)

## Usage
Run `python server.py` to start the Flask server for local usage.
At the moment this software has not been tested for WSGI deployment.
I would advise not deploying to a production enviroment in its current state.

## Pages
Below is a list of pages or endpoints available:
* Home
* Login/Signup
* Logout (does not render a page, logs out and redirects)
* Accounts directory
    * Individual account page
* Change Cash (Banker only, quick access for accounts)
* Bank Transfer (Banker only)
* Properties directory
    * Individual property
    * Individual property API endpoint
* Error pages
    * 404
    * 403
* SSE event signal endpoint

## Development Environment
This software is built using Python, Flask, and a Flask extension called Flask-Login.
Both of these libraries must be in your Python environment to successfully run.

The development environment targets a Linux system.
There have been little attempts to test on other operating systems;
some breakage has been reported on Windows.

## Useful Websites
Websites that have been useful in the development of this project:
* [Python Flask Documentation](https://flask.palletsprojects.com/en/2.2.x/)
* [Python Flask-Login Documentation](https://flask-login.readthedocs.io/en/latest/)
* [Monopoly Properties List](https://www.monopolyland.com/monopoly-properties-list-with-prices/)

## Future Work
* More proper server API endpoints to enable native applications
* Better server sent events (SSE) to send changes without full page reload
* Refactor to not use OOP-like design
