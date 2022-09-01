# How to Release

1.  Use `bump2version` to bump the version number.

    -   If a minor / major version is needed:

        -   `bump2version minor` or `bump2version major`

    -   Then release the version: `bump2version release`

2.  Edit the `CHANGELOG.md` file.

    -   Change unreleased to the version number you are releasing.

    -   Add `(YYYY-MM-DD)` date next to version number.

    -   Add link to the full changelog. 

3.  Commit and push the changes.

4.  Make a release on GitHub (and create a tag). This will automatically upload the new package to PyPI.

5.  Publish the new version on Readthedocs.

6.  Use `bump2version` to create a new beta version: `bump2version patch`
