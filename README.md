# Cuckoo: A Custom Confluence Importer for Outline
This is the result of:
- needing to migrate from Confluence
- madness and
- lack of sleep.

As a result, the code is bad, unoptimized, and doesn't work for everything.
I will change that (and publish this repository at some point), but for now, it's private.

This README is just for the entertainment of whoever wants to look through the commit history. Have fun!

Tested with Confluence 9.2.4 and Outline 0.87.3

## How to use Cuckoo
1. Download Cuckoo from the Releases
2. Create a file named `.env`. This is best done by copying `sample.env` and adjusting the values to your needs
3. Export desired spaces from your Confluence instance as HTML
4. Run `import.py <export_zip_1> <export_zip_2> ... <export_zip_n>`<br>Cuckoo will handle all of the files
5. Be mindful of API rate limits: If the script runs into the rate limit, it aborts. This is subject to change.

## Known Issues
- User profile pictures are not kept. This is intentional: Due to how they're stored, this would need a separate implementation for these attachments.<br>While keeping them intact is possible, I opted for the simpler solution (for now) to get the main content converted quickly.
- Images don't work as link anchors. I didn't find an option to make an image a hyperlink in the editor, so I'm assuming Outline to be incapable of using something other than text as anchor.
