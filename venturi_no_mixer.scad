// ─────────────────────────────────────────────────────────────
// Passive Venturi iNO Delivery Device — Parametric OpenSCAD
// Author: Tyler "The TimeLord" Roost
// Date:   2026-03-05
// License: The Time License v2.0 — see LICENSE
//
// No electronics. No sensors. No software. No power.
// Concentration set by machined geometry.
// Rotate the cap → change the orifice area → change the ppm.
//
// BOM: tube body, oval-orifice cap, soda lime cartridge,
//      NO/N₂ gas cartridge (800 ppm), nasal cannula adapter.
// ─────────────────────────────────────────────────────────────

// ── PARAMETERS (all mm) ────────────────────────────────────

// Tube body
tube_od       = 26;      // outer diameter
tube_id       = 22;      // inner diameter (mixing chamber bore)
tube_wall     = (tube_od - tube_id) / 2;
tube_length   = 90;      // total barrel length

// Oval orifice (venturi throat) — between dime (17.9mm) and nickel (21.2mm)
oval_width    = 15;      // minor axis (horizontal)
oval_height   = 10;      // major axis (vertical)
throat_depth  = 3;       // thickness of the orifice plate

// Cap (twist-to-dose)
cap_od        = tube_od + 4;  // slight overhang for grip
cap_length    = 18;           // length of the cap section
cap_id        = tube_od + 0.3; // slip fit over tube body
cap_grip_depth = 1.0;         // knurling depth

// Side port (NO/N₂ cartridge connection)
port_od       = 8;       // outer diameter of side port nipple
port_id       = 5;       // inner bore — sized for 800ppm NO/N₂ flow
port_length   = 12;      // protrusion length
port_angle    = 90;      // perpendicular to tube axis
port_z_pos    = 20;      // distance from inlet end to port center

// Soda lime scrubber chamber (inline, between mixer and output)
scrubber_length = 25;    // length of scrubber section
scrubber_id     = tube_id - 2; // slightly narrower to hold granule mesh
mesh_wall       = 1;     // retaining mesh wall thickness

// Output adapter (smooth taper from tube OD to nasal cannula)
adapter_od_base = tube_od;   // flush with tube exterior
adapter_od_tip  = 5;
adapter_length  = 15;

// Dose detents (click positions for 5, 10, 20, 40, 80 ppm)
n_detents     = 5;
detent_depth  = 0.5;
detent_radius = 0.8;

// Print settings
$fn = 80;  // facet count for smooth curves
tol = 0.15; // printer tolerance

// ── MODULES ────────────────────────────────────────────────

module oval(w, h) {
    // 2D oval (ellipse) centered at origin
    scale([w/2, h/2]) circle(r=1);
}

module tube_body() {
    difference() {
        union() {
            // Main barrel
            cylinder(d=tube_od, h=tube_length);

            // Side port nipple
            translate([0, 0, port_z_pos])
                rotate([0, 90, 0])
                    cylinder(d=port_od, h=tube_od/2 + port_length);
        }

        // Bore through barrel
        translate([0, 0, -1])
            cylinder(d=tube_id, h=tube_length + 2);

        // Side port bore
        translate([0, 0, port_z_pos])
            rotate([0, 90, 0])
                cylinder(d=port_id, h=tube_od/2 + port_length + 1);

        // Venturi throat (oval constriction at inlet end)
        // The throat is the narrowest point — creates the vacuum
        translate([0, 0, port_z_pos - throat_depth/2])
            linear_extrude(height=throat_depth)
                difference() {
                    circle(d=tube_id + 1);
                    oval(oval_width, oval_height);
                }

        // Scrubber chamber (wider section at output end for soda lime)
        translate([0, 0, tube_length - scrubber_length - adapter_length])
            cylinder(d=scrubber_id + 2*mesh_wall, h=scrubber_length);

        // Scrubber mesh retainer grooves (two rings to hold filter discs)
        translate([0, 0, tube_length - scrubber_length - adapter_length])
            cylinder(d=tube_id + 1, h=mesh_wall);
        translate([0, 0, tube_length - adapter_length - mesh_wall])
            cylinder(d=tube_id + 1, h=mesh_wall);

        // Detent track on exterior (for cap clicks)
        for (i = [0 : n_detents - 1]) {
            angle = i * (360 / n_detents);
            rotate([0, 0, angle])
                translate([tube_od/2, 0, 8])
                    sphere(r=detent_radius);
        }
    }
}

module dose_cap() {
    // Twist cap with oval port — rotation controls exposed orifice area
    difference() {
        union() {
            // Cap shell
            cylinder(d=cap_od, h=cap_length);

            // Grip texture (simplified knurling — vertical ribs)
            for (i = [0 : 23]) {
                rotate([0, 0, i * 15])
                    translate([cap_od/2 - cap_grip_depth/2, 0, 0])
                        cylinder(d=cap_grip_depth, h=cap_length);
            }
        }

        // Hollow interior (slips over tube body)
        translate([0, 0, -1])
            cylinder(d=cap_id, h=cap_length + 2);

        // Oval orifice through cap wall
        // This is the key: as you rotate the cap, the oval
        // aligns more or less with the tube's side port,
        // controlling how much vacuum is transmitted
        translate([0, 0, cap_length/2])
            rotate([90, 0, 0])
                linear_extrude(height=cap_od)
                    oval(oval_width * 0.8, oval_height * 0.8);

        // Dose indicator line (engraved)
        translate([cap_od/2 - 0.3, 0, cap_length - 2])
            cube([0.6, 0.6, 3], center=true);
    }

    // Detent spring bump (catches in tube body grooves)
    translate([cap_id/2 - 0.3, 0, 8])
        sphere(r=detent_radius * 0.8);
}

module cannula_adapter() {
    // Smooth taper from tube bore to nasal cannula tip
    difference() {
        cylinder(d1=adapter_od_base, d2=adapter_od_tip, h=adapter_length);
        translate([0, 0, -1])
            cylinder(d1=tube_id, d2=3,
                     h=adapter_length + 2);
    }
}

module scrubber_disc() {
    // Perforated retainer disc for soda lime granules
    difference() {
        cylinder(d=scrubber_id, h=mesh_wall);
        // Perforation pattern
        for (r = [0, 3, 6]) {
            for (a = [0 : 30 : 359]) {
                rotate([0, 0, a + r*5])
                    translate([r, 0, -0.5])
                        cylinder(d=1.5, h=mesh_wall + 1);
            }
        }
    }
}

module dose_label() {
    // Text labels for ppm settings (engrave on cap exterior)
    ppm_values = ["5", "10", "20", "40", "80"];
    for (i = [0 : n_detents - 1]) {
        angle = i * (360 / n_detents);
        rotate([0, 0, angle])
            translate([cap_od/2 + 0.5, 0, cap_length/2])
                rotate([90, 0, 90])
                    linear_extrude(height=0.4)
                        text(ppm_values[i], size=3, halign="center",
                             valign="center", font="Liberation Sans:style=Bold");
    }
}

// ── ASSEMBLY ───────────────────────────────────────────────

module full_assembly() {
    // Tube body (main component)
    color("WhiteSmoke") tube_body();

    // Dose cap (shown in position, rotated to 20 ppm default)
    color("DodgerBlue", 0.8)
        rotate([0, 0, 2 * (360 / n_detents)])  // detent position 2 = 20 ppm
            dose_cap();

    // Cannula adapter (press-fit at output end)
    color("WhiteSmoke")
        translate([0, 0, tube_length])
            cannula_adapter();

    // Scrubber discs (two, shown in position)
    color("Gold", 0.5) {
        translate([0, 0, tube_length - scrubber_length - adapter_length])
            scrubber_disc();
        translate([0, 0, tube_length - adapter_length - mesh_wall])
            scrubber_disc();
    }

    // Dose labels
    color("Black") dose_label();
}

// ── PRINT PLATES ───────────────────────────────────────────
// Uncomment ONE section to export for printing.

// Option 1: Full assembly (preview only)
full_assembly();

// Option 2: Tube body (print flat)
// tube_body();

// Option 3: Dose cap (print upright)
// translate([tube_od + 10, 0, 0]) dose_cap();

// Option 4: Cannula adapter
// translate([0, tube_od + 10, 0]) cannula_adapter();

// Option 5: Scrubber discs (print 2)
// translate([-tube_od - 10, 0, 0]) scrubber_disc();

// Option 6: All parts on plate (for printing)
// tube_body();
// translate([tube_od + 10, 0, 0]) dose_cap();
// translate([0, tube_od + 10, 0]) cannula_adapter();
// translate([-tube_od - 10, 0, 0]) scrubber_disc();
// translate([-tube_od - 10, tube_od, 0]) scrubber_disc();
