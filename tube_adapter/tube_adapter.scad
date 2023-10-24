$fn=80;

// units are mm

deep=20;
overlap=60;
d_inner = 1.9*25.4;
inner_fudge=0.5;
d_outer = 93;

d_bulge=105;
d_bulge_slot=96;
bulge_length=10;
d_bulge_slot_length=4;

extension_length=60;

taper_depth=40;
stop_shelf_width=(d_inner-1.590*25.4)/2;

simple_mode=false;

if (simple_mode) {
    echo("Building in simple mode");
    deep = deep/2;
    extension_length = extension_length/3;
    difference(){
        union() {
            cylinder(deep, d=d_outer, center=false);
            translate([0,0,deep]) cylinder(extension_length, d1=d_outer, d2=d_inner, center=false);
        }
        cylinder(deep+extension_length, d=d_inner+inner_fudge, center=false);
    }
} else {
    echo("Building in non-simple mode");
    difference(){
        union(){
            cylinder(deep, d=d_outer, center=false);
            translate([0,0,deep]) difference() {
                cylinder(bulge_length, d=d_bulge, center=false);
                difference() {
                    cylinder(d_bulge_slot_length, d=d_bulge_slot, center=false);
                    cylinder(d_bulge_slot_length, d=d_outer, center=false);
                }
            }
            translate([0,0,deep+bulge_length]) cylinder(extension_length, d1=d_bulge, d2=d_inner, center=false);
        }
        cylinder(taper_depth, d1=d_outer, d2=d_inner-2*stop_shelf_width, center=false);
        translate([0,0,taper_depth]) cylinder(deep+bulge_length+extension_length-taper_depth, d=d_inner+inner_fudge, center=false);
    }
}
