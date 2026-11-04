#!/usr/bin/env python3
"""College angles at the closing line, FBS vs FBS, split 2021-23 / 2024-25 to see what holds.
Usage: python3 scripts/backtest_cfb_angles.py  (reads cfb_hist.csv, a CollegeFootballData games export with lines)
Result (Nov 4, 2026): unders on totals of 58+ 384-315 (54.9%) | 170-133 (56.1%); this season 7-10.
Home dogs +3..+7 57.7% | 53.1%, but 50.8% at true home games in 2024-25, so not used. Everything else ~50%."""
import csv, collections, statistics as st
from datetime import datetime
R=[]
for r in csv.DictReader(open('cfb_hist.csv')):
    try:
        if int(r['season'])<2021 or r['home_division']!='fbs' or r['away_division']!='fbs': continue
        sp=float(r['home_spread']); tl=float(r['total_line']) if r['total_line'] else None
        hp,ap=float(r['home_points']),float(r['away_points'])
    except: continue
    d=datetime.fromisoformat(r['start_date'].replace('Z','+00:00'))
    R.append(dict(s=int(r['season']),wk=int(r['week']),neutral=r['neutral_site']=='True',conf=r['conference_game']=='True',sp=sp,tl=tl,m=hp-ap,tot=hp+ap,
      month=d.month, wd=d.weekday(), hour=(d.hour-5)%24, he=float(r['home_pregame_elo'] or 0), ae=float(r['away_pregame_elo'] or 0), hc=r['home_conference'], ac=r['away_conference'], post=r['season_type']!='regular', home=r['home_team'], away=r['away_team'], date=d))
print(len(R))
def side(x, pick_home):   # 1 win 0 loss None push
    c=x['m']+x['sp']
    if c==0: return None
    return (c>0)==pick_home
def tot(x, over):
    if x['tl'] is None or x['tot']==x['tl']: return None
    return (x['tot']>x['tl'])==over
def show(name, f):
    out={}
    for part,ss in (('2021-23',(2021,2022,2023)),('2024-25',(2024,2025))):
        res=[f(x) for x in R if x['s'] in ss]; res=[v for v in res if v is not None]
        w=sum(res); out[part]=(w,len(res)-w, 100*w/len(res) if res else 0)
    a,b=out['2021-23'],out['2024-25']
    flag = '  <==' if a[2]>=53 and b[2]>=53 and a[0]+a[1]>=80 and b[0]+b[1]>=60 else ''
    print(f'{name:55s} {a[0]:4d}-{a[1]:<4d} {a[2]:5.1f}% | {b[0]:4d}-{b[1]:<4d} {b[2]:5.1f}%{flag}')
G5={'Mountain West','Mid-American','Conference USA','Sun Belt','American Athletic','FBS Independents'}
P4={'SEC','Big Ten','Big 12','ACC','Pac-12'}
show('home dogs', lambda x: side(x,True) if x['sp']>0 else None)
show('road dogs', lambda x: side(x,False) if x['sp']<0 else None)
show('home dogs +3..+7', lambda x: side(x,True) if 3<=x['sp']<=7 else None)
show('home dogs +7.5..+14', lambda x: side(x,True) if 7.5<=x['sp']<=14 else None)
show('big dogs +17+', lambda x: (side(x,True) if x['sp']>=17 else side(x,False) if x['sp']<=-17 else None))
show('big dogs +21+', lambda x: (side(x,True) if x['sp']>=21 else side(x,False) if x['sp']<=-21 else None))
show('big dogs +28+', lambda x: (side(x,True) if x['sp']>=28 else side(x,False) if x['sp']<=-28 else None))
show('conf game home dog', lambda x: side(x,True) if x['sp']>0 and x['conf'] else None)
show('nonconf big dog 14+', lambda x: (side(x,True) if x['sp']>=14 else side(x,False) if x['sp']<=-14 else None) if not x['conf'] else None)
show('unders all', lambda x: tot(x,False))
show('unders total 60+', lambda x: tot(x,False) if x['tl'] and x['tl']>=60 else None)
show('unders total 65+', lambda x: tot(x,False) if x['tl'] and x['tl']>=65 else None)
show('overs total <42', lambda x: tot(x,True) if x['tl'] and x['tl']<42 else None)
show('overs total <45', lambda x: tot(x,True) if x['tl'] and x['tl']<45 else None)
show('unders November', lambda x: tot(x,False) if x['month']==11 else None)
show('unders Nov/Dec total 50+', lambda x: tot(x,False) if x['month'] in (11,12) and x['tl'] and x['tl']>=50 else None)
show('unders weekday (Tue-Fri) games', lambda x: tot(x,False) if x['wd'] in (1,2,3,4) else None)
show('overs weekday (Tue-Fri) games', lambda x: tot(x,True) if x['wd'] in (1,2,3,4) else None)
show('MAC unders', lambda x: tot(x,False) if x['hc']=='Mid-American' and x['ac']=='Mid-American' else None)
show('MAC weekday unders', lambda x: tot(x,False) if x['hc']=='Mid-American' and x['wd'] in (1,2,3,4) else None)
show('unders big spread (|sp|>=21)', lambda x: tot(x,False) if abs(x['sp'])>=21 else None)
show('overs big spread (|sp|>=21)', lambda x: tot(x,True) if abs(x['sp'])>=21 else None)
show('unders close game (|sp|<=3)', lambda x: tot(x,False) if abs(x['sp'])<=3 else None)
show('unders night (8pm+ ET)', lambda x: tot(x,False) if x['hour']>=20 else None)
show('unders noon games', lambda x: tot(x,False) if x['hour']<=12 else None)
show('home favs -3..-7', lambda x: side(x,True) if -7<=x['sp']<=-3 else None)
show('road favs', lambda x: side(x,False) if x['sp']>0 else None)
show('P4 vs G5 G5 dog', lambda x: (side(x,True) if x['hc'] in G5 and x['ac'] in P4 and x['sp']>0 else side(x,False) if x['ac'] in G5 and x['hc'] in P4 and x['sp']<0 else None))
show('bowl dogs', lambda x: (side(x,True) if x['sp']>0 else side(x,False)) if x['post'] else None)
show('late season (wk 10+) home dogs', lambda x: side(x,True) if x['sp']>0 and x['wk']>=10 and not x['post'] else None)
show('late season (wk 10+) unders', lambda x: tot(x,False) if x['wk']>=10 and not x['post'] else None)
show('early season (wk<=4) overs', lambda x: tot(x,True) if x['wk']<=4 else None)
print('--- refinements (judge on both halves) ---')
show('home dogs +3..+7 conf', lambda x: side(x,True) if 3<=x['sp']<=7 and x['conf'] else None)
show('home dogs +3..+7 nonconf', lambda x: side(x,True) if 3<=x['sp']<=7 and not x['conf'] else None)
show('home dogs +3..+7 not neutral', lambda x: side(x,True) if 3<=x['sp']<=7 and not x['neutral'] else None)
show('unders 60+ |sp|<=10', lambda x: tot(x,False) if x['tl'] and x['tl']>=60 and abs(x['sp'])<=10 else None)
show('unders 60+ |sp|>10', lambda x: tot(x,False) if x['tl'] and x['tl']>=60 and abs(x['sp'])>10 else None)
show('unders 58+', lambda x: tot(x,False) if x['tl'] and x['tl']>=58 else None)
show('unders 62+', lambda x: tot(x,False) if x['tl'] and x['tl']>=62 else None)
