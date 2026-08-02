# LaTeX build report

- Timestamp: `2026-08-02T12:32:50`
- Entry: `latex/main.tex`
- Output: `latex/main.pdf`
- Engine: `latexmk -xelatex -bibtex`
- Page count: `10`
- Goal page target: `8-10 total PDF pages`

## Result

- Status: SUCCESS
- Message: SUCCESS

## Warning summary

- underfull_hbox: 2

## Stdout (tail)

```
Rc files read:
  NONE
Latexmk: This is Latexmk, John Collins, 27 Dec. 2024. Version 4.86a.
Latexmk: applying rule 'xdvipdfmx'...
Rule 'xdvipdfmx':  Reasons for rerun
Category 'no_dest':
  xdvipdfmx

------------
Run number 1 of rule 'xdvipdfmx'
------------
------------
Running 'xdvipdfmx -E -o "main.pdf"  "main.xdv"'
------------
Latexmk: All targets (main.xdv main.pdf) are up-to-date

```

## Stderr (tail)

```
main.xdv -> main.pdf
[1][2][3][4][5][6][7][8][9
xdvipdfmx:warning: Object @table.1 already defined.
][10]
93300 bytes written
```
