citSupport is a Python Module providing support for manage continuous integration builds.

It contains two main sub-modules:
  monitoredRepo - monitor a GitHub repo for push events,
  testRun - execute a sequence of shell commands to build and test

In order to access what may be protected repository information, this application needs to be able to authenticate
itself to GitHub, and in order to do so, it uses a personal API token, which it assumes is contained in the
environment variable GHRPAT.

see:
https://developer.github.com/guides/basics-of-authentication
https://developer.github.com/v3/auth/#basic-authentication
https://developer.github.com/v3/oauth_authorizations/
https://developer.github.com/v3/oauth/
https://github.com/blog/1509-personal-api-tokens