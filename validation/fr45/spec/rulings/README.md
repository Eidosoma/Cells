# FR-45's rulings and the lead's records, copied into the registration

**These files are the lead's.** They are copied here so that the tagged registration is self-contained, as FR-43 part
3's judge committed its rulings. Each is byte-identical to its source in `/mnt/workspaces/Cells/fr45-readings-20261126/`.
None holds a reference value, and the cross-check's output holds key paths only.

| File | sha256, equal to its source's |
| --- | --- |
| `RULINGS-1-2026-11-26.md` | 09e7986b5b8255b06add387fbaca10a2ab7945ac54501bfc5783aa015dee5a9e |
| `RULINGS-2-2026-11-27.md` | 6f194bbad6b9fc93a20aec42611b84cad02e3b09706040b6eedafd8d8545edef |
| `CENSUS-2026-11-27.txt` | 5aabb892ca7fedbc9322c044e626150b6a9c3ccf63afe2f93e9912fec41687eb |
| `REFERENCE-FORMAT-NOTE-2026-11-27.txt` | 5747d381ad795c98072630878b793256b9e61fffd6f39fabb92acdae90eceb00 |
| `CROSSCHECK-5-2026-11-27.txt` | a967ee18bd09b5babf4f5f9c4dd024d06687b8c76980c90e088c5bae301b18c9 |

- **Pointers.** `validation/fr45/spec/TABLE.md`'s pointers to RULINGS-2, and to RULINGS-1, the census and the
  references' format note beside it, resolve to these copies. The other files that RULINGS-2 names beside itself, such
  as the reader's `sentences.md` and the census scripts, stay in the source folder.
- **Held: `crosscheck_expected.py`.** The lead's cross-check script, which wrote `CROSSCHECK-5-2026-11-27.txt`, is not
  copied yet. Its line 4 names the lead's local checkout by an absolute path that the public repository's privacy scan
  bars, so a byte-identical copy cannot pass that scan. It is added when the lead gives a copy without that path, or
  rules otherwise.
