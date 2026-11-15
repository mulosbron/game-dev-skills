import sand3d as s3d


def ruin():
    wall=s3d.at(broken_wall(),x=0,y=0,z=0)
    base=s3d.at(bottom_ledge(),x=0,y=0,z=0)
    return s3d.assembly("ruin",wall,base)


def broken_wall(t=100,waist=2000,low=-600):
    profiles=[]
    for x,yt,zt,ym,yz,yb,zb in [(-2650,-3500,4800,-1600,-500,0,low),(-1100,-3850,4000,-2400,-1300,-300,low),(0,-4640,4300,-3050,-1650,-650,-550),(1050,-5600,5100,-3700,-1800,-100,-1100),(1550,-5370,4670,-4000,-1950,235,-1420),(2550,-5500,4100,-4200,-2050,1800,-2600)]:
        path=s3d.spline([(yt,zt),(ym,waist),(yz,0),(yb,zb)])
        profiles.append(s3d.at(s3d.stroke(path,t=t),on=s3d.Frame(origin=(x,0,0),normal=(1,0,0),up=(0,0,1))))
    solid=s3d.loft("wall",*profiles)
    s3d.material(solid,"concrete",color="#b0aaa0")
    return s3d.group("broken_wall",solid)


def bottom_ledge(t=50, floor=-2650):
    profiles=[]
    for x,ya,za,yb in [(-2600,1000,-1400,2800),(-1100,1800,-1850,2640),(0,2500,-2400,2780),(1050,2140,-2200,2600),(2600,-500,-1200,1800)]:
        path=s3d.spline([(ya,za),(yb,floor)])
        profiles.append(s3d.at(s3d.stroke(path,t=t),on=s3d.Frame(origin=(x,0,0),normal=(1,0,0),up=(0,0,1))))
    solid=s3d.loft("ledge",*profiles)
    s3d.material(solid,"concrete",color="#b0aaa0")
    upright=s3d.at(end_upright(),x=0,y=0,z=0)
    return s3d.group("bottom_ledge",solid,upright)


def end_upright(t=50):
    profiles=[]
    for x,yb,zb,ym,zm,yt,zt in [(-2600,2500,-2600,1100,-1300,2200,850),(-1100,2640,-2640,1800,-1850,3100,230),(0,2780,-2700,2520,-2400,3800,-100),(1050,2600,-2670,2140,-2200,3700,-300),(2600,1800,-2600,1500,-2000,2800,450)]:
        path=s3d.spline([(yb,zb),(ym,zm),(yt,zt)])
        profiles.append(s3d.at(s3d.stroke(path,t=t),on=s3d.Frame(origin=(x,0,0),normal=(1,0,0),up=(0,0,1))))
    solid=s3d.loft("upright",*profiles)
    s3d.material(solid,"concrete",color="#b0aaa0")
    strip=s3d.at(curved_strip(),x=0,y=0,z=0)
    return s3d.group("end_upright",solid,strip)


def curved_strip(t=100):
    profiles=[]
    for x,yb,zb,ym,zm,yt,zt in [(-2600,1200,-1600,-400,0,-500,400),(-1100,-300,-600,-1200,950,330,2050),(0,-650,-550,-100,0,1200,1600),(1050,-100,-1100,1000,-100,1640,1080),(2550,1800,-2600,0,-1300,1900,400)]:
        path=s3d.spline([(yb,zb),(ym,zm),(yt,zt)])
        profiles.append(s3d.at(s3d.stroke(path,t=t),on=s3d.Frame(origin=(x,0,0),normal=(1,0,0),up=(0,0,1))))
    solid=s3d.loft("strip",*profiles)
    s3d.material(solid,"concrete",color="#b0aaa0")
    return s3d.group("curved_strip",solid)
