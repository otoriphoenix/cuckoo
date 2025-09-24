# Cuckoo: A Custom Confluence Importer for Outline
This is the result of:
- needing to migrate from Confluence
- madness and
- lack of sleep.

As a result, the code is bad, unoptimized, and doesn't work for everything.
I will change that (and publish this repository at some point), but for now, it's private.

This README is just for the entertainment of whoever wants to look through the commit history. Have fun!

Tested with Confluence 9.2.4 and Outline 0.87.3

## Known Issues
- User profile pictures are not kept. This is intentional: Due to how they're stored, this would need a separate implementation for these attachments.<br>While keeping them intact is possible, I opted for the simpler solution (for now) to get the main content converted quickly.
