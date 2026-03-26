# LLM-BIDS (Exploratory)

Small semi-automatic BIDSification pipeline based on a structured user–LLM agent interaction.

## Important privacy note

Make sure the LLM is **not allowed to access raw data content** if there is any risk of sending sensitive information to third-party servers.

## Current idea

1. Analyze raw input data structure.
2. Define tools and environment (**user validation required**).
3. Build the pipeline by reusing an existing project structure:
   1. Rebuild the BIDS tree (correct paths and filenames).
   2. Verify all files are accounted for, including subject/session counts (**user validation required**).
   3. Run BIDS validation and collect errors (for example with https://pypi.org/project/bids-validator/, Docker-based validation/logging, or online validation).
   4. Iterate on file-level transformation scripts with the user.

## Notes

- This is an exploratory approach, not a fully autonomous conversion system.
- The scripted and standardized pipeline remains the reference implementation.
