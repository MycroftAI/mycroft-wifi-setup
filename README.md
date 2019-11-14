# Mycroft WiFi Setup

This repository holds Mycroft's wifi setup client. To build it, run `./build.sh`. To create a deb package, after building it run `./package_deb.sh`. The results are placed into the `dist/` folder.

## Environment setup
To upload to the repository using scp the environment variables `REPO_USER` and `REPO_URL` needs to be set before running the publish scripts.
