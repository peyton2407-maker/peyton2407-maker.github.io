#!/usr/bin/env python3
"""College spread picks from a power rating (CFBD pregame Elo standing in for ESPN FPI), blended
75% line / 25% rating like the site, graded against closing spreads, 2020-2025.
Usage: python3 scripts/backtest_cfb_potd.py cfb_hist.csv   (CFBD games export with lines)
Result (Oct 29, 2026): 1.6-pt bar 458-503 (47.7%); 2.0 46.6%; 3.0 44.3%; biggest gap each week 33-35."""
import csv, math, statistics as st
rows=[]
for r in csv.DictReader(open(__import__('sys').argv[1] if len(__import__('sys').argv) > 1 else 'cfb_hist.csv')):
    try:
        he,ae=float(r['home_pregame_elo']),float(r['away_pregame_elo']); sp=float(r['home_spread']); hp,ap=float(r['home_points']),float(r['away_points'])
    except: continue
    tl=float(r['total_line']) if r['total_line'] else None
    rows.append(dict(season=int(r['season']),week=int(r['week']),neutral=r['neutral_site']=='True',d=he-ae,sp=sp,m=hp-ap,tot=hp+ap,tl=tl,conf=r['conference_game']=='True'))
print(len(rows),'games')
# fit margin = a*eloDiff + b*home on 2015-2019
tr=[x for x in rows if x['season']<=2019]
import numpy as np
X=np.array([[x['d'], 0 if x['neutral'] else 1] for x in tr]); y=np.array([x['m'] for x in tr])
coef,*_=np.linalg.lstsq(X,y,rcond=None); a,b=coef; print('fit: pts per elo %.4f  hfa %.2f'%(a,b))
te=[x for x in rows if x['season']>=2020]
def run(MW, floor, rows):
    w=l=p=0; units=0
    for x in rows:
        rating=-(a*x['d']+(0 if x['neutral'] else b))   # as a home spread
        blended=MW*x['sp']+(1-MW)*rating
        edge=x['sp']-blended                              # >0 = home side
        if abs(edge)<floor: continue
        cover=x['m']+x['sp']                              # >0 home covered
        if cover==0: p+=1; continue
        win=(cover>0)==(edge>0)
        w+=win; l+=not win
    n=w+l
    return w,l,p,(w/n if n else float('nan'))
for floor in (0.5,1.0,1.6,2.0,3.0,4.0):
    w,l,p,r=run(0.75,floor,te)
    print('2020-25 floor %.1f: %d-%d-%d  %.1f%%  units %+.1f' % (floor,w,l,p,100*r, w*0.909-l))
# biggest-edge pick per week (like a play of the day)
by={}
for x in te:
    rating=-(a*x['d']+(0 if x['neutral'] else b)); blended=0.75*x['sp']+0.25*rating; edge=x['sp']-blended
    by.setdefault((x['season'],x['week']),[]).append((abs(edge),edge,x))
w=l=0
for k,v in by.items():
    v.sort(key=lambda t:-t[0]); e,edge,x=v[0]
    if e<1.6: continue
    cover=x['m']+x['sp']
    if cover==0: continue
    if (cover>0)==(edge>0): w+=1
    else: l+=1
print('biggest edge each week: %d-%d %.1f%%'%(w,l,100*w/(w+l)))
