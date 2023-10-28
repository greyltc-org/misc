$fn=80;

// units are mm
// schedule 40 1.5 inch pipe is OD=1.9 in., ID=1.590 in.
// fan shroud OD=~96mm

d_over_fan_max = 120;
d_over_fan_min=96;
l_below=30;
l_above=60;
shelf_pos=40;

tube_id = 1.590*25.4;
tube_od = 1.9*25.4;
tube_od_fudge=0.5;


difference(){
    union(){
        mirror([0,0,1]) cylinder(h=l_below, d1=d_over_fan_max, d2=d_over_fan_min,center=false);
        cylinder(h=l_above, d1=d_over_fan_max, d2=tube_od+tube_od_fudge,center=false);
    }
    translate([0,0,-l_below]) cylinder(h=l_below, d=d_over_fan_min, center=false);
    translate([0,0,shelf_pos]) cylinder(h=l_below+l_above, d=tube_od+tube_od_fudge, center=false);
    cylinder(h=shelf_pos, d1=d_over_fan_min, d2=tube_id, center=false);
}
