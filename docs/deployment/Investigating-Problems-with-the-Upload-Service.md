## Investigating Problems with Submissions

Problems with Upload usually start with someone saying "I uploaded a file but it never appeared in the Ingest Submission Envelope" or "my file never went valid".  There is a useful tool to figure out what went on with a particular file or submission: `dcpdig`.

`dcpdig` is part of the `dcp-diag` package:

```
pip install dcp-diag
```

The, given an upload area UUID (which you can get from the "Data" tab of a submission in the Ingest UI), run:
```
dcpdig -d dev @upload area=<uuid> --show all
```