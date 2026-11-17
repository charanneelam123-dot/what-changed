# A short project post

I built a small tool called What changed? for comparing a renewal with the previous
version.

The sample agreement raises the rent by $125 a month. It also doubles the moving
notice period and adds a package fee. The report puts each edit beside the original
clause, including the source line numbers.

The optional model step explains edits and suggests questions, but it has to supply
quotes that actually appear in the files. Python handles the diff and arithmetic.

One detail I chose to leave out: a grand total. The tool cannot tell whether an
optional parking charge applies to the reader, so showing one number would hide
an assumption.

Code: https://github.com/charanneelam123-dot/what-changed

The examples are fictional. Live-model behavior still needs testing.
