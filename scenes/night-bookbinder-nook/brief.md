# night-bookbinder-nook (DRAFT, awaiting owner sign-off)

First local AnyScene test. Goal: prove the local pipeline end to end on a small set, about 1 h of GPU for generation.

## Place
A tiny bookbinder's workshop in a Lisbon side street, 11 PM, light rain outside. A shop that has been in the same
family for forty years: tight, tidy-messy, warm.

**Mood:** warm, cramped, papery, quiet, lived-in.

## Room
3.2 m wide (x) by 4.0 m deep (y) by 2.6 m high. Street door and one small shop window at y=0, room deep along +Y.
Pitched shelf wall on the left (x low), big work table in the middle, press and cutting corner at the back.

## Zones
- Front: door, window with a few books on display, a small counter stool.
- Middle: heavy work table under a pendant lamp.
- Back: standing book press, paper cutter, tool wall, shelving with paper rolls.

## Hero spots (camera)
1. From the door looking down the room toward the press, wide, 24 mm.
2. Over the work table, close, 50 mm, rack from the bone folder to the half-sewn book.
3. Low, 30 cm off the floor, along the table legs and stool (floating-prop check).

## Practicals
Brass pendant lamp over the table, an angled desk lamp on the work table, a warm glow from the window sign, cool
street spill through the glass, a dim bulb at the back.

## Generated props (14, heights in metres, no brand names; furniture and walls are scripted)
| id | prop | h |
|---|---|---|
| book_press | cast-iron standing book press with a big wheel | 1.10 |
| paper_cutter | guillotine paper cutter, wood and iron | 0.55 |
| sewing_frame | wooden bookbinding sewing frame with threads | 0.50 |
| desk_lamp | angled metal desk lamp | 0.45 |
| pendant_lamp | brass dome pendant lamp | 0.35 |
| paper_roll_rack | rack holding rolls of marbled paper | 0.90 |
| stool | worn wooden counter stool | 0.65 |
| glue_pot | enamel glue pot with brush | 0.18 |
| bone_folder_set | tool jar with bone folders and awls | 0.20 |
| leather_stack | stack of dyed leather hides | 0.25 |
| book_stack | stack of old cloth-bound books | 0.30 |
| thread_spools | wooden box of waxed thread spools | 0.12 |
| old_radio | small wooden tube radio | 0.28 |
| plant_pot | potted fern in a chipped clay pot | 0.45 |

Hero props (generated at higher care): book_press, paper_cutter, sewing_frame. Mid: lamps, rack, stool, radio, plant.
Clutter: the rest. Density sells realism more than size does: pile the table.

## Plan for the run
1. Concept wide and detail (Krea 2), owner agrees the look.
2. 14 references with the scan template, check for brands, then TRELLIS 2 and Pixal3D (about 2.5-5 min each).
3. Compare page (`node pipeline/build_compare_page.mjs --config page.json`), pick per prop.
4. Prep, shell, dress, light, 2-3 shots with AnyShot (see the `anyshot-local` skill).
Open question for the owner: keep both generators for all 14 (about 1 h) or TRELLIS 2 alone (about 40 min)?
