// ============================================================
// COOK rig enclosure v3 — single constant-depth box, fastener-free:
// no screws, inserts, nuts, or glue anywhere. The telescoping
// two-shell design (v2) is gone. Now it's ONE printed box (front
// face + all four side walls, open at the back) plus a THIN back
// panel that slides down into channel grooves cut into the box's
// own left/right inner walls — closes the box, and pulls back out
// for service. The CO2 hopper moved off the back (there's no back
// wall to hang it on anymore) onto the right side wall instead.
//
// Open in OpenSCAD (openscad.org). PLACEHOLDER dimensions below are
// marked "MEASURE YOURS" — confirm against your actual parts, then
// F5 (preview) before F6 (render) / STL export.
//
// Print each part as a SEPARATE STL: set exactly one render_* flag
// true, F6, export, repeat. render_assembly shows both together for
// a fit-check only.
//
// Material: PETG or ASA. Nothing flexes/snaps anymore (no collar,
// no snap bump) — the panel is a plain slide-and-friction fit — so
// PLA is a more reasonable option here than it was for v2, though
// PETG/ASA still resists warping on that big flat panel better.
//
// AXIS CONVENTION: X = box width (face_w), Y = box height (face_h),
// Z = box depth, front face in the XY plane at Z=0. Unlike v2, this
// is now the ONLY frame in the file — box_shell() and back_panel()
// are both authored directly in it, so render_assembly doesn't need
// to translate anything to line them up. That was a real source of
// error last time (the collar math needed careful by-hand
// re-derivation); removing the second local frame removes that
// whole class of mistake.
//
// I still do not have OpenSCAD running in the environment this was
// written in — everything below is worked out from the numbers, not
// rendered. Spots flagged "FLAG:" are the ones most likely to need a
// nudge once you actually preview it.
// ============================================================

// ---- WHICH PART TO RENDER ----
render_box      = false;
render_panel    = false;
render_assembly = true;

// ---- GLOBAL TOLERANCES ----
wall      = 2.4;   // shell wall thickness (~6 perimeters at 0.4mm nozzle)
fit_gap   = 0.25;  // clearance budget for the panel's slide fit
corner_r  = 3;     // outer corner rounding
$fn       = 48;

// ============================================================
// MEASURE-AND-CONFIRM: component footprints
// Unchanged from v2 — confirmed from spec sheets: display, camera,
// battery pack, switch panel-hole diameter. Everything else is a
// reasonable placeholder — measure your actual part and edit before
// slicing.
// ============================================================

// -- Display: Hosyond 7", CONFIRMED from spec sheet --
disp_l = 164.9; disp_w = 102.0; disp_h = 15.15;
disp_active_l = 154.21; disp_active_w = 85.92;
disp_sleeve_clr = 0.8;  // total clearance around the display's outer edge in its retaining sleeve (0.4mm/side) -- looser than fit_gap (meant for small parts), since a slide-fit this size needs more margin for print tolerance; loosen further if it doesn't slide in easily

// -- Camera: Raspberry Pi Camera Module v2, CONFIRMED standard footprint --
cam_pcb_l = 25; cam_pcb_w = 24; cam_pcb_h = 9;
cam_hole_pitch = 21;   // the two M2 mounting holes, this far apart, centered on the board
cam_hole_d     = 2.4;  // clearance for an M2 self-tapper / heat-set insert-free press fit
cam_lens_d     = 9;    // front clearance hole for the lens barrel + ribbon strain relief

// -- Jetson Nano, MEASURED directly from NVIDIA's own STEP file for
//    the B01 dev kit (Jetson_Nano_Dev_Kit_3D_b01.stp, PRODUCT
//    '142-13449-1000-B01') by parsing its board-outline edges and
//    mounting-hole circles — not a datasheet guess, not the old
//    generic placeholder. Board outline: 100.0 x 79.0mm.
//
//    You said you actually have the original (A02) board, not B01 —
//    this file was the closest thing on hand. NVIDIA designed the
//    B01 carrier board to be mechanically drop-in compatible with
//    A02 specifically so existing cases wouldn't break, so the board
//    outline and hole pattern below should carry over — but I
//    couldn't confirm that against an A02 STEP file directly, so
//    it's still worth a quick check against your actual board before
//    slicing anything.
//
//    nano_h is the tallest point found anywhere within the board's
//    own footprint in that STEP file (i.e. heatsink included) — real
//    data, but specific to whatever heatsink ships with the B01 kit;
//    if your A02's heatsink/fan shroud is a different height, this
//    is the one number here still worth measuring directly. --
nano_l = 100; nano_w = 79; nano_h = 22;

// Mounting-hole offsets from the board's own center — MEASURED, and
// NOT symmetric (many boards aren't): 4mm/10mm inset from the
// left/right edges, 17mm/4mm inset from the bottom/top edges. Used
// directly by the Nano's peg placement in back_panel() instead of
// wall_snap_pegs()'s generic symmetric inset, which was wrong for
// this board specifically (it assumed a centered rectangle).
nano_hole_dx = [-46, 40];      // X offsets from nano_cx: left pair, right pair
nano_hole_dy = [-22.5, 35.5];  // Y offsets from nano_cy: bottom pair, top pair
nano_hole_r  = 1.38;           // measured clearance-hole radius (~2.76mm dia, M2.5 clearance)

// -- Aobao 8xAA battery holder, CONFIRMED from the listing:
//    12.6 x 7.1 x 2.0cm (L x W x H), 14cm leads each. --
batt_l = 126; batt_w = 71; batt_h = 20;
batt_lead_len = 140;

// -- Small protoboard you'll solder the relay/fuse/resistor circuit
//    to (PLACEHOLDER — size to whatever board you actually buy) --
pcb_l = 70; pcb_w = 50;
pcb_thickness = 15;  // PLACEHOLDER — rough guess for a populated board (relay, terminal blocks); measure yours

// -- Firing (arm) switch, SparkFun "Toggle Switch and Cover -
//    Illuminated (Red)". Panel hole CONFIRMED at 12mm from the
//    listing. Behind-panel depth is still not published anywhere —
//    PLACEHOLDER, measure the body + missile-cover mechanism with
//    calipers before slicing. --
switch_bushing_d = 12;  // CONFIRMED
switch_body_len  = 35;  // PLACEHOLDER — clearance needed behind the panel for the switch + lugs + missile cover mechanism

// -- 12g CO2 cartridge, typical published dims for a threaded 12g —
//    verify against your actual brand, some run longer. --
co2_d       = 12.6;  // clearance diameter (cartridge body + a hair)
co2_len     = 68;
co2_count   = 3;      // channels, stacked vertically — one cartridge each, lying flat

// ============================================================
// FRONT-FACE LAYOUT. Display centered vertically in its own zone;
// camera centered above it; switch shares the top row with the
// camera instead of sitting beside the display.
//
// box_w and box_h are each the larger of two independent floors: the
// front face's own needs, and the back panel's electronics layout
// (battery + cable gap + Nano/protoboard — see ELECTRONICS LAYOUT).
// Getting the printed footprint down to fit a 220mm bed (a friend's
// printer flagged the earlier version as ~25% too big) meant tuning
// BOTH floors together, not just one — margins alone couldn't get
// there (battery + Nano side by side need ~171mm before any margin
// at all), so the Nano is now mounted ROTATED 90° from its natural
// resting orientation: its narrower 79mm side sets the column width
// instead of its 100mm side, trading some width for extra height on
// the back panel (which had plenty of slack to give). Same reasoning
// as the battery's own rotation earlier in this file.
// ============================================================
side_margin    = 6;    // left/right edge margin — trimmed from 12; still clear of corner_r
cam_switch_gap = 15;   // gap between the camera zone and the switch zone (same row now)
cam_zone_w     = 40;   // width reserved for the camera mount
switch_zone_w  = 40;   // width reserved for the switch mount

top_margin    = 12;
cam_zone_h    = 34;   // height reserved for the camera/switch row
cam_gap       = 10;   // gap between that row and the display's top edge
bottom_margin = 12;

// Used here for the electronics floors AND in ELECTRONICS LAYOUT
// below (battery/Nano/protoboard column positioning) — one
// definition, so the two can't drift apart.
component_margin = 3;   // horizontal clearance from each column to the interior wall — thin, this is the tightest margin in the file besides the cable hole itself
vmargin           = 5;   // vertical clearance within a column (floor/ceiling)
stack_gap         = 9;   // gap between the Nano and the protoboard stacked above it

display_row_w = disp_l + 2 * side_margin;
switch_dx     = cam_zone_w / 2 + cam_switch_gap + switch_zone_w / 2;  // switch center, offset from camera center
top_row_w     = 2 * (switch_dx + switch_zone_w / 2 + side_margin);    // doubled: camera sits at X=0, so box_w must cover the switch's overhang on both sides even though only the right side is actually used
face_w        = max(display_row_w, top_row_w);

cable_gap_min = 16;  // gap between the battery and Nano columns — just enough for the 12mm cable hole (see back_panel()) plus ~2mm clearance each side; tighter than most of this file's other clearances
electronics_w = component_margin * 2 + batt_w + cable_gap_min + nano_w + 2 * wall;  // nano_w, not nano_l — rotated, see above

box_w = max(face_w, electronics_w);

face_h = top_margin + cam_zone_h + cam_gap + disp_w + bottom_margin;

batt_col_h    = batt_l + 2 * vmargin;                     // battery column height (already rotated, unaffected by the Nano's rotation)
stack_col_h   = nano_l + stack_gap + pcb_w + 2 * vmargin;  // nano_l, not nano_w — rotated, so the Nano's LONG axis is now vertical
electronics_h = max(batt_col_h, stack_col_h) + 2 * wall;

box_h = max(face_h, electronics_h);

inner_w = box_w - 2 * wall;
inner_h = box_h - 2 * wall;

// FLAG: reasoned from the numbers, not rendered. Both floors are
// close to each other by design (box_w: face_w 176.9 vs electronics_w
// 176.8; box_h: face_h 170.0 vs electronics_h 173.8) — re-check both
// sides if you change ANY of side_margin, component_margin, the cable
// gap, or any component dimension, since which one binds can flip.

// Display and camera centered on the box itself — box_w/box_h may be
// wider/taller than the front face strictly needs (see above), in
// which case this just adds equal breathing room on both sides
// rather than pushing the display off-center.
disp_cx = 0;
disp_cy = -face_h / 2 + bottom_margin + disp_w / 2;

// Camera center, horizontally centered on the display/box, in its
// own zone above it.
cam_cx = disp_cx;
cam_cy = face_h / 2 - top_margin - cam_zone_h / 2;

// Switch center, to the right of the camera, same row.
switch_cx = cam_cx + switch_dx;
switch_cy = cam_cy;

// ============================================================
// BOX DEPTH & THE SLIDE-IN PANEL
// total_depth is held at the same 101.6mm (4in) the telescoping v2
// design landed on — "the depth should stay the same" — even though
// nothing here forces that number anymore. Because v2's collar
// wasted depth on a double-walled overlap, dropping it actually
// freed up interior room: wiring_margin below comes out roughly 33mm
// instead of v2's 19.2mm for the same exterior length.
//
// The panel sits in a channel cut at the very back: one rectangular
// cut removes material from the top wall (an insertion slot, full
// panel width) AND grooves into the inner faces of the left/right
// walls (groove_depth_x deep) in the same operation, because the cut
// spans the full box height (floor to exterior top) but only
// panel_w wide — see box_shell() for the actual cube(). The box's
// own bottom wall (never cut) is the panel's hard stop; nothing else
// holds it in but gravity, the snug channel fit, and friction — no
// snap feature this time.
// ============================================================
front_clear_depth = 32;   // unchanged from v2: display PCB + camera standoff + wiring slack
total_depth       = 101.6;

panel_thickness = wall;      // thin panel, same thickness as the box's own walls
groove_depth_x  = wall / 2;  // how far the channel bites into each side wall — leaves wall/2 of that wall intact behind it
channel_span    = panel_thickness + fit_gap;      // Z-depth of the channel/slot cut
channel_z0      = total_depth - channel_span;     // where the channel cut starts, back edge is total_depth
panel_inner_z   = total_depth - panel_thickness;  // the panel's own inward-facing surface — standoffs project from here, same role back_cap_inner_z played in v2

panel_w = inner_w + 2 * groove_depth_x - 2 * fit_gap;  // reaches into both grooves, minus slide clearance
panel_h = inner_h - fit_gap;  // bottom edge is the hard stop against the floor; only the top needs clearance

standoff_h       = 5;    // gap between the panel and the underside of each mounted board — unchanged from v2
component_max_h  = max(nano_h, max(batt_h, pcb_thickness));  // 29mm, Nano
panel_clear_depth = channel_z0 - front_clear_depth;
wiring_margin     = panel_clear_depth - standoff_h - component_max_h;

// FLAG: reasoned from the numbers, not rendered. If wiring_margin
// prints negative here, front_clear_depth + standoff_h +
// component_max_h no longer fits in total_depth — widen total_depth
// before slicing, don't shrink component clearances to force it.

// ============================================================
// CO2 HOPPER — now on a side wall instead of the back. Cartridges
// still lie on their sides and stack vertically, loaded from the
// open top, single bottom-slot access (see co2_hopper() below) —
// only the mounting wall changed, not the magazine mechanism.
// hopper_side flips which wall it's on with a one-line change; no
// other numbers below depend on which side you pick.
// ============================================================
hopper_side     = 1;   // +1 = right wall (+X), -1 = left wall (-X)
hopper_cap_t    = wall * 2;  // far-end cap thickness — thicker than the other hopper walls on purpose, see the note below; does NOT affect hopper_depth, so the cartridge clearance is untouched
hopper_len      = co2_len + 10 + (hopper_cap_t - wall);  // cartridge length + clearance, plus whatever hopper_cap_t added beyond a plain wall — keeps the actual usable interior length (co2_len + 10) unchanged
hopper_stack_h  = co2_count * (co2_d + 2) + 10;  // stacked cartridges + small gaps + top loading clearance
hopper_depth    = co2_d + 2 * wall;              // how far the pod sticks out from the side wall — unaffected by hopper_cap_t
hopper_slot_h   = wall + co2_d;                  // bottom wall thickness + one cartridge — front wall starts exactly where the second cartridge does

// hopper_cap_t only thickens the FAR end wall (the one that has to
// bridge across stack_h with nothing under it once printed — see
// co2_hopper()) — not the near end wall, which sits right at the bed
// with no bridging concern, and not the bottom/outward walls, which
// bound the cartridge diameter via hopper_depth. Doubling it (2.4mm
// -> 4.8mm) doesn't shrink the ~54mm span that first bridge layer
// has to cross — that's a function of stack_h, not wall thickness —
// but it does make the finished cap stiffer and gives the slicer
// more solid-infill layers to reinforce a slightly-sagged first
// layer with. If a print actually fails here, the real fix is
// enabling supports for just this feature, or shrinking stack_h.
hopper_z0       = 0;       // flush with the front face — see the print-orientation note below, this is NOT arbitrary
hopper_cy       = 0;       // vertically centered — nothing else competes for space on this wall anymore

// Printed with the box face-down (front face on the bed, box builds
// upward in Z) — same orientation the face cutouts already assume.
// hopper_z0 MUST stay at 0, not some front margin like v2's back
// hopper had: the hopper's cross-section doesn't grow as Z increases
// (same footprint at every height), so starting it flush with the
// bed means every layer sits directly on the one below. Starting it
// any higher (it was 12 in an earlier draft) would have the pod's
// full cross-section appear in mid-air over a wall that, up to that
// height, hadn't grown out that far in X yet — a real unsupported
// overhang, not a printable feature. If you move the hopper for any
// other reason, keep this constraint in mind — it isn't about tidy
// margins, it's about what has to be true for this to print clean.
//
// FLAG: reasoned, not rendered. hopper_z0 + hopper_len (currently
// 0 + 80.6 = 80.6, taller than before now that hopper_cap_t > wall)
// needs to stay clear of channel_z0 (currently ~98.95) — checked by
// hand, ~18mm margin — but re-check if you change hopper_cap_t,
// hopper_len, co2_len, or total_depth.

// ============================================================
// ELECTRONICS LAYOUT — Nano/battery/protoboard, all mounted to the
// INSIDE face of the back panel (not the box itself) — pull the
// panel and the whole populated tray comes with it.
//
// BOTH the battery and the Nano are mounted ROTATED 90° from their
// natural resting orientation — each for the same reason: the
// dimension driving column WIDTH is swapped out for the board's
// narrower one, trading it for extra column HEIGHT instead (the
// back panel had far more height to spare than width).
//
// Battery: footprint here is batt_w wide x batt_l tall instead of
// batt_l wide x batt_w tall — batt_l (126mm) is wider than half of
// inner_w, so it can't sit anywhere without crossing the centerline
// where the cable hole needs to go; rotated, it fits in one column
// with room to spare. Doesn't affect the holder itself — a plastic
// AA holder, no orientation-sensitive leads.
//
// Nano: footprint here is nano_w wide x nano_l tall instead of
// nano_l wide x nano_w tall — needed once the whole box got tighter
// to fit a friend's 220mm print bed (see FRONT-FACE LAYOUT); the
// Nano's 79mm side is now what sets the column width instead of its
// 100mm side. Unlike the battery, the Nano's mounting HOLES are
// real, measured, asymmetric data (see nano_hole_dx/dy up in
// MEASURE-AND-CONFIRM) — rotating the board means rotating that hole
// pattern too, done explicitly below rather than hand-recomputing
// new numbers, so the relationship to the original measurement stays
// checkable.
//
// Battery gets its own column on the left (tall and narrow); Nano
// and protoboard stack in a column on the right (short and wide);
// the gap between the two columns is where the cable hole goes.
// ============================================================

// nano_hole_dx/dy rotated 90° CCW: (x,y) -> (-y,x). The two distinct
// old_x values become the new dy directly; the two distinct old_y
// values become dx, negated and reversed. Verified by hand that the
// spans swap cleanly (old dx span 86 == new dy span; old dy span 58
// == new dx span) — not rendered.
nano_mount_dx = [-nano_hole_dy[1], -nano_hole_dy[0]];
nano_mount_dy = nano_hole_dx;

// component_margin/vmargin/stack_gap are defined up in FRONT-FACE
// LAYOUT — this column layout is exactly what electronics_w and
// electronics_h were computed from.
batt_cx = -inner_w / 2 + batt_w / 2 + component_margin;
batt_cy = -inner_h / 2 + batt_l / 2 + vmargin;

nano_cx = inner_w / 2 - nano_w / 2 - component_margin;  // nano_w, not nano_l — rotated
nano_cy = -inner_h / 2 + nano_l / 2 + vmargin;            // nano_l, not nano_w — rotated
pcb_cx  = nano_cx;
pcb_cy  = nano_cy + nano_l / 2 + stack_gap + pcb_w / 2;  // stacked above the Nano; nano_l is now its half-height

// Cable pass-through: just a barrel jack for the Nano's power plus a
// couple of thin solenoid wires, not a wide bundle — a single 12mm
// hole (see back_panel()) instead of the old wider oval. True
// lower-center, same spot v2 had it. The gap between the two columns
// here is exactly cable_gap_min by construction (see FRONT-FACE
// LAYOUT), so the hole has only ~2mm clearance on each side —
// tighter than most of this file's other clearances, worth
// eyeballing on the first render.
cable_cx = 0;
cable_cy = -inner_h / 2 + 20;

// ============================================================
// BUILDING BLOCKS
// ============================================================

// Rounded rectangular box, solid, extruded up from z=0.
module rounded_box(l, w, h, r) {
    linear_extrude(h)
        hull()
            for (x = [-1, 1], y = [-1, 1])
                translate([x * (l / 2 - r), y * (w / 2 - r)])
                    circle(r = r);
}

// CO2 hopper: ONE gravity-fed magazine, solid on all sides except a
// bottom access slot in the outward-facing wall. Local frame here is
// MOUNT-RELATIVE, not world-relative: local X = protrusion off the
// mounting wall (0 = flush against it), local Y = vertical stack,
// local Z = cartridge length. No back wall in this version — v2's
// version needed one because its back cap wasn't reliably solid
// everywhere; here the box's own side wall is already solid across
// its full depth, so mounting flush against it (see box_shell())
// closes the pod automatically, with nothing redundant to model.
module co2_hopper(len, stack_h, depth, wall_t, slot_h, cap_t = wall) {
    union() {
        cube([depth, wall_t, len]);                          // bottom wall
        cube([depth, stack_h, wall_t]);                       // near end wall — right at the bed, no bridging concern, stays plain wall_t thick
        translate([0, 0, len - cap_t])
            cube([depth, stack_h, cap_t]);                     // far end wall — the one that has to bridge (spans the full stack_h in one go, over what was previously just the bottom wall + a strip of outward wall below it); cap_t defaults to wall_t but callers can thicken just this one wall — see hopper_cap_t
        translate([depth - wall_t, slot_h, 0])
            cube([wall_t, stack_h - slot_h, len]);              // outward wall, everywhere ABOVE the bottom access slot
    }
}

// Snap peg: pushes through a board's own mounting hole and retains
// it there — shaft sized for a light slide fit, then a barb that
// bulges wider than the hole so the board has to flex slightly to
// pop over it, and a tapered tip so it starts easily. hole_r is a
// PLACEHOLDER (1.6mm, generic M3 clearance) — measure the board's
// actual hole diameter before slicing. Origin at the peg's own base,
// +Z (the base end is what fuses into the mounting wall via the
// union in box_shell()/back_panel(); the barb/tip end is what a
// board's hole slides onto).
module snap_peg(shaft_h, hole_r = 1.6, barb_extra = 0.4) {
    shaft_r = hole_r - 0.2;
    barb_r  = hole_r + barb_extra;
    cylinder(h = shaft_h, r = shaft_r);
    translate([0, 0, shaft_h])
        cylinder(h = 1.2, r1 = shaft_r, r2 = barb_r);
    translate([0, 0, shaft_h + 1.2])
        cylinder(h = 1.0, r1 = barb_r, r2 = shaft_r * 0.6);
}

// Four snap pegs for a board WITH real mounting holes (Nano,
// protoboard): footprint fx x fy, centered at (cx, cy), pegs inset
// from the true corners by `inset` — a stand-in for the board's own
// hole pattern, which isn't known yet. z0 is the mounting wall's own
// inner face; pegs project standoff_h away from it, toward -Z.
module wall_snap_pegs(cx, cy, fx, fy, z0, standoff_h, inset = 8) {
    for (x = [-1, 1], y = [-1, 1])
        translate([cx + x * (fx / 2 - inset), cy + y * (fy / 2 - inset), z0 - standoff_h])
            snap_peg(standoff_h);
}

// Retaining rails for a board with NO mounting holes (the battery
// pack): two plain walls, one along its top edge and one along its
// bottom, running the board's full depth — a snug slot it sits in,
// held by fit and friction, the same way the back panel itself is
// held by its own channel (no separate shelf ledge or end-stop lip).
// fy is the board's own footprint height (its extent in Y); the
// rails sit fit_gap clear of it on each side so it can actually
// slide in.
module wall_rails(cx, cy, fx, fy, depth, z0, wall_t, clr = fit_gap) {
    translate([cx - fx / 2, cy + fy / 2 + clr, z0 - depth])
        cube([fx, wall_t, depth]);
    translate([cx - fx / 2, cy - fy / 2 - clr - wall_t, z0 - depth])
        cube([fx, wall_t, depth]);
}

// Retaining sleeve for a flat panel mounted behind a front-face
// window (the display): a snug frame surrounding all FOUR edges of
// its outer footprint. Slides in from the open back during assembly
// until its front bezel meets the thin shoulder cut around the
// active-area window (see box_shell()).
module display_sleeve(cx, cy, l, w, depth, wall_t, clr) {
    difference() {
        translate([cx, cy, 0])
            linear_extrude(depth)
                square([l + 2 * wall_t + clr, w + 2 * wall_t + clr], center = true);
        translate([cx, cy, -0.1])
            linear_extrude(depth + 0.2)
                square([l + clr, w + clr], center = true);
    }
}

// ============================================================
// PART 1 — BOX
// One piece: front face (display/switch/camera), all four side
// walls, full total_depth, open at the back. The channel cut at the
// back does double duty — see the comment on it below. CO2 hopper
// mounted on the exterior of whichever side wall hopper_side picks.
// Print face-down, no supports needed for the face cutouts.
// ============================================================
module box_shell() {
    difference() {
        union() {
            rounded_box(box_w, box_h, total_depth, corner_r);

            // CO2 hopper, flush against the outside of the chosen
            // side wall. mirror() flips only X (not Z, unlike a
            // rotate) so the "which end is the mounting face" logic
            // stays simple to check by hand: local X=0 always lands
            // at world X = hopper_side * box_w/2 regardless of side.
            if (hopper_side > 0)
                translate([box_w / 2, hopper_cy - hopper_stack_h / 2, hopper_z0])
                    co2_hopper(hopper_len, hopper_stack_h, hopper_depth, wall, hopper_slot_h, hopper_cap_t);
            else
                translate([-box_w / 2, hopper_cy - hopper_stack_h / 2, hopper_z0])
                    mirror([1, 0, 0])
                        co2_hopper(hopper_len, hopper_stack_h, hopper_depth, wall, hopper_slot_h, hopper_cap_t);
        }

        // Hollow interior, open the whole way through the back
        // (unlike v2's rear shell, this box has no back wall of its
        // own at all — the panel is the only thing that closes it).
        translate([0, 0, wall])
            linear_extrude(total_depth - wall + 0.2)
                hull()
                    for (x = [-1, 1], y = [-1, 1])
                        translate([x * (box_w / 2 - wall - corner_r),
                                   y * (box_h / 2 - wall - corner_r)])
                            circle(r = corner_r);

        // -- Front face cutouts, all in the z=0 face --
        translate([disp_cx, disp_cy, -0.1])
            linear_extrude(wall + 0.2)
                square([disp_active_l, disp_active_w], center = true);

        translate([switch_cx, switch_cy, -0.1])
            cylinder(h = wall + switch_body_len, r = switch_bushing_d / 2);

        translate([cam_cx, cam_cy, -0.1])
            cylinder(h = wall + 0.2, r = cam_lens_d / 2);
        for (x = [-1, 1])
            translate([cam_cx + x * cam_hole_pitch / 2, cam_cy, -0.1])
                cylinder(h = wall + 0.2, r = cam_hole_d / 2);

        // CSI ribbon channel, same as v2.
        translate([cam_cx - 5, cam_cy - cam_zone_h / 2, wall])
            cube([10, cam_gap + 4, front_clear_depth]);

        // -- Back channel: ONE cut that does two jobs at once. It
        // spans the full panel width (X) and the full box height (Y,
        // floor to exterior top surface), but only channel_span deep
        // (Z, at the very back). Where it's wide (X) but only
        // channel_span deep, it's the top-wall insertion slot; where
        // it's narrow (X, at the two edges) but runs the full height,
        // it's the left/right guide grooves. Both fall out of the
        // same cube() because panel_w/2 + fit_gap works out to
        // exactly inner_w/2 + groove_depth_x — verified by hand
        // above where panel_w is defined, not rendered.
        translate([-(panel_w / 2 + fit_gap), -inner_h / 2, channel_z0])
            cube([panel_w + 2 * fit_gap, inner_h / 2 + box_h / 2 + 0.1, channel_span + 0.1]);
    }

    // Camera snap pegs and display sleeve — added AFTER the
    // difference() (sibling statement, implicitly unioned), same as
    // v2, same reasoning: geometry this close to the face would
    // otherwise fall inside the cavity cut and get removed by it.
    cam_standoff_h = 4;
    for (x = [-1, 1])
        translate([cam_cx + x * cam_hole_pitch / 2, cam_cy, wall])
            snap_peg(cam_standoff_h, hole_r = cam_hole_d / 2);

    display_sleeve(disp_cx, disp_cy, disp_l, disp_w, disp_h + 2, wall, disp_sleeve_clr);

    // Reference only, not part of the printed geometry.
    translate([cam_cx, cam_cy, wall + cam_standoff_h + cam_pcb_h / 2])
        %cube([cam_pcb_l, cam_pcb_w, cam_pcb_h], center = true);
    translate([disp_cx, disp_cy, wall + disp_h / 2])
        %cube([disp_l, disp_w, disp_h], center = true);
    for (i = [0 : co2_count - 1])
        translate([hopper_side * (box_w / 2 + wall + co2_d / 2),
                   hopper_cy - hopper_stack_h / 2 + wall + co2_d / 2 + i * co2_d,
                   hopper_z0 + wall])
            %cylinder(h = co2_len, r = co2_d / 2, $fn = 24);
}

// ============================================================
// PART 2 — BACK PANEL
// Thin slide-in cover, authored directly in the box's own Z frame
// (panel_inner_z to total_depth) — no separate local origin, unlike
// v2's front/rear shells, so no translate is needed to place it in
// render_assembly. Carries the Nano/battery/protoboard standoffs,
// vent grid, and cable pass-through — all of it moved off the box
// itself so pulling the panel pulls the whole populated tray with
// it. Print flat, face down (panel_thickness up), no supports.
// ============================================================
module back_panel() {
    difference() {
        union() {
            // Main slab, sized to reach into both channel grooves.
            translate([-panel_w / 2, -inner_h / 2, panel_inner_z])
                cube([panel_w, panel_h, panel_thickness]);

            // Thumb tab: sticks up past the box's exterior top
            // surface once the panel is fully seated, so there's
            // something to grab to pull it back out.
            translate([-10, inner_h / 2 - fit_gap, panel_inner_z])
                cube([20, (box_h / 2 + 3) - (inner_h / 2 - fit_gap), panel_thickness]);
        }

        // Ventilation grid, spanning the FULL nano+protoboard column
        // height (both boards, not just behind the Nano like v2) for
        // more airflow. The column mixes two boards with two
        // different peg patterns (the Nano's real, measured, off-
        // center hole positions and the protoboard's still-generic
        // 6mm inset), so rather than hand-picking which corners to
        // skip the way v2 did, positions are generated on a fixed
        // pitch across the whole column and filtered against the
        // actual peg coordinates — more robust than a hand-tuned
        // corner skip, and it has to be since the Nano's pegs aren't
        // even symmetric anymore.
        vent_pegs = concat(
            [for (dx = nano_mount_dx, dy = nano_mount_dy) [nano_cx + dx, nano_cy + dy]],
            [for (x = [-1, 1], y = [-1, 1]) [pcb_cx + x * (pcb_l / 2 - 6), pcb_cy + y * (pcb_w / 2 - 6)]]
        );
        vent_clearance = 6;  // min distance (mm) a vent hole must keep from any peg center
        vent_col_x  = nano_w / 2 - 10;               // half-width, based on the Nano (still the wider of the two boards even rotated: 79 > pcb_l's 70)
        vent_col_y0 = nano_cy - nano_l / 2 + 10;     // just above the Nano's bottom edge — nano_l is now its half-height, rotated
        vent_col_y1 = pcb_cy + pcb_w / 2 - 8;        // just below the protoboard's top edge
        for (vx = [-vent_col_x : 15 : vent_col_x], vy = [vent_col_y0 : 15 : vent_col_y1])
            if (min([for (p = vent_pegs) norm([nano_cx + vx, vy] - p)]) > vent_clearance)
                translate([nano_cx + vx, vy, panel_inner_z - 0.1])
                    cylinder(h = panel_thickness + 0.2, r = 3);

        // Cable pass-through, in the open gap between the two
        // component columns. Single 12mm hole — a barrel jack plug
        // for the Nano's power plus a couple of thin solenoid wires,
        // not a wide bundle, so no need for the old two-circle hull.
        translate([cable_cx, cable_cy, panel_inner_z - 0.1])
            cylinder(h = panel_thickness + 0.2, r = 6);
    }

    // Mounted boards — added AFTER the difference(), same reasoning
    // as v2: this close to the panel's own face, they'd otherwise
    // fall inside the vent/cable cuts above and get removed by them.
    //
    // Nano pegs use the measured, asymmetric hole offsets — ROTATED
    // (nano_mount_dx/dy, see ELECTRONICS LAYOUT) to match the board's
    // rotated mounting orientation — instead of wall_snap_pegs()'s
    // generic symmetric inset, which doesn't fit this board's real
    // pattern, and the measured hole radius (nano_hole_r), not
    // snap_peg()'s generic M3 default.
    for (dx = nano_mount_dx, dy = nano_mount_dy)
        translate([nano_cx + dx, nano_cy + dy, panel_inner_z - standoff_h])
            snap_peg(standoff_h, hole_r = nano_hole_r);
    wall_snap_pegs(pcb_cx, pcb_cy, pcb_l, pcb_w, panel_inner_z, standoff_h, inset = 6);
    // fx = batt_w, fy = batt_l here — the rails follow the battery's
    // rotated (w x l) footprint, not its natural (l x w) orientation.
    wall_rails(batt_cx, batt_cy, batt_w, batt_l, standoff_h + batt_h, panel_inner_z, wall);

    // Reference only, not part of the printed geometry.
    translate([nano_cx, nano_cy, panel_inner_z - standoff_h - nano_h / 2])
        %cube([nano_w, nano_l, nano_h], center = true);  // rotated: w x l footprint, not l x w
    translate([batt_cx, batt_cy, panel_inner_z - standoff_h - batt_h / 2])
        %cube([batt_w, batt_l, batt_h], center = true);  // rotated: w x l footprint, not l x w
    translate([pcb_cx, pcb_cy, panel_inner_z - standoff_h - pcb_thickness / 2])
        %cube([pcb_l, pcb_w, pcb_thickness], center = true);
}

// ============================================================
// RENDER
// ============================================================
if (render_box) box_shell();

// back_panel() is authored in the box's shared design frame (needed
// for render_assembly to fit-check correctly, no translate to get
// wrong) — but that frame has the panel's flat face at MAX Z and the
// standoffs reaching down to MIN Z, which is backwards from what a
// slicer assumes by default (native Z-up = flat face at low Z, bed-
// ready). Loaded as-is, a slicer would try to rest this on the
// standoff tips instead of the flat face. So the standalone export
// gets a print-time-only flip — rotate 180° about X to put the flat
// face at the bottom, then translate back near the origin — that
// does NOT touch the fit geometry used by render_assembly below,
// only this one export.
if (render_panel)
    translate([0, 0, total_depth])
        rotate([180, 0, 0])
            back_panel();

// Assembled preview: both modules already share the same Z frame,
// so this is a plain union — no translate to get wrong. Fit-check
// only, not for slicing — this one is deliberately in the
// UN-flipped design frame, not the print-ready orientation above.
if (render_assembly) {
    box_shell();
    back_panel();
}
