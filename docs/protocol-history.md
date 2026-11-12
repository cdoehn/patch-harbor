# Historical protocol documents

The active contract is [Task 2 / Execute JSON 2 / Result 4](protocol-2.md).
The [Result-2](result-format-2.md) and [Result-3](result-format-3.md) documents
are retained unchanged as historical descriptions of their original releases.
Their historical words “current” or “production” do not describe version 2.0.0.
Original fixture archives and historical plans likewise retain their bytes.

The current reader does not accept these older generations, and no filename
change, runtime bootstrap, CLI alias or ScriptBundle converts them. Upgrade
callers deliberately and obtain a fresh Result from the actual repository.
