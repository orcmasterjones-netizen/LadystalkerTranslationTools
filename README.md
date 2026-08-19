# LadystalkerTranslationTools
ChatGPT created tools for updating the Ladystalker translation.

To use:
1. Open ladystalker_script_workspace.tsv in Excel, LibreOffice, or another TSV-compatible editor.
2. Find a row, for example: message_id: 0x0000
  Japanese: その 方向には 何もない<WAIT_INPUT>
  Machine English: There's nothing that way.<WAIT_INPUT>
3. Enter your replacement only in the professional_translation column:
   Nothing lies in that direction.<WAIT_INPUT> (keep the WAIT_INPUT command there)
4. Leave the Japanese and machine-reference columns untouched. Blank professional-translation cells automatically retain the machine translation.
5. Save the file as UTF-8 TSV.
6. Apply Lady_Stalker_ENG_v10.ips to the original Japanese ROM first. Then, from inside the extracted kit’s deliverables directory, run:
   py ladystalker_reinsert.py ^
  "Lady_Stalker_ENG_v10.sfc" ^
  "ladystalker_script_workspace.tsv" ^
  "ladystalker_lookup_workspace.tsv" ^
  --output-ips "Lady_Stalker_Professional_Translation.ips" ^
  --output-rom "Lady_Stalker_Professional_Test.sfc"
   or if using Windows Powershell, run:
   py ladystalker_reinsert.py "Lady_Stalker_ENG_v10.sfc" "ladystalker_script_workspace.tsv" "ladystalker_lookup_workspace.tsv" --output-ips "Lady_Stalker_Professional_Translation.ips" --output-rom "Lady_Stalker_Professional_Test.sfc"

7. That Windows command creates:

Lady_Stalker_Professional_Translation.ips — the distributable overlay patch.
Lady_Stalker_Professional_Test.sfc — a private testing ROM.

The overlay IPS must be applied to the already ENG-v1.0-patched ROM.



Formatting controls

Keep tags such as these exactly where needed:

<SPEAKER>
<INSERT_A>
<NUMBER>
<WAIT>
<WAIT_INPUT>
<PAUSE_30>
<CLEAR>
<LINE>

A real line break inside the spreadsheet cell becomes the normal in-game newline:

This is the first line.
This is the second line.<WAIT_INPUT>

The compiler will refuse accidental changes to important controls. It also rejects unsupported characters instead of silently mangling them.

For names and items, do the same thing in ladystalker_lookup_workspace.tsv. For example:

Japanese: コックス
Machine reference: Cox
Professional translation: Cox

One limitation: the compiler verifies encoding, controls, ROM space, pointers, and checksum, but it cannot know whether a sentence visually overflows the dialogue box. Long lines still need an emulator playtest and manual line breaks. 👊
