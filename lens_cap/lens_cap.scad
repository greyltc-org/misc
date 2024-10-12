$fn=70;
inner_d=42;
wall_t=2;
end_t=4;
height=20;
difference() {
    cylinder(h=height+end_t,r=(inner_d+2*wall_t)/2);
    translate([0,0,end_t]) cylinder(h=height,r=(inner_d)/2);
}