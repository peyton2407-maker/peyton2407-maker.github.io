#!/usr/bin/env python3
"""More college angles at the closing line, FBS vs FBS, 2021-23 | 2024-25 (run Nov 7, 2026, no Odds API calls).
Usage: python3 scripts/backtest_cfb_angles2.py  (reads cfb_hist.csv, the CollegeFootballData export used by backtest_cfb_angles.py)
Result: the under edge is 58+ only (54-57.5 went 51%); rest, bye, look-ahead, letdown, bounce-back and key-number
spreads all ~47-53% or split between halves. Backing a team off an upset win as a 10+ dog went 52.6% | 52.8%: too thin to
beat -110. Nothing new added."""
import csv, collections
from datetime import datetime
R=[]
for r in csv.DictReader(open('cfb_hist.csv')):
    try:
        if int(r['season'])<2021: continue
        fbs = r['home_division']=='fbs' and r['away_division']=='fbs'
        sp=float(r['home_spread']); tl=float(r['total_line']) if r['total_line'] else None
        hp,ap=float(r['home_points']),float(r['away_points'])
    except: continue
    d=datetime.fromisoformat(r['start_date'].replace('Z','+00:00'))
    R.append(dict(s=int(r['season']),wk=int(r['week']),fbs=fbs,neutral=r['neutral_site']=='True',conf=r['conference_game']=='True',sp=sp,tl=tl,m=hp-ap,tot=hp+ap,
      wd=d.weekday(),hour=(d.hour-5)%24,he=float(r['home_pregame_elo'] or 0),ae=float(r['away_pregame_elo'] or 0),hc=r['home_conference'],ac=r['away_conference'],
      post=r['season_type']!='regular',home=r['home_team'],away=r['away_team'],date=d,hp=hp,ap=ap))
R.sort(key=lambda x:x['date'])
# per-team schedule: previous and next game
sched=collections.defaultdict(list)
for x in R:
    sched[(x['s'],x['home'])].append(x); sched[(x['s'],x['away'])].append(x)
def prevnext(x,team):
    L=sched[(x['s'],team)]; i=L.index(x)
    return (L[i-1] if i>0 else None),(L[i+1] if i+1<len(L) else None)
for x in R:
    for side,team in (('h',x['home']),('a',x['away'])):
        p,n=prevnext(x,team)
        x[side+'rest']=(x['date']-p['date']).days if p else None
        if p:
            mine = p['hp'] if p['home']==team else p['ap']; opp = p['ap'] if p['home']==team else p['hp']
            spm = -p['sp'] if p['home']==team else p['sp']   # my spread last game (negative = I was favored)
            x[side+'prev_m']=mine-opp; x[side+'prev_sp']=spm
        else: x[side+'prev_m']=None; x[side+'prev_sp']=None
        if n:
            ne = n['ae'] if n['home']==team else n['he']; x[side+'next_elo']=ne
        else: x[side+'next_elo']=None
R=[x for x in R if x['fbs']]
def side(x, home):
    c=x['m']+x['sp']
    if c==0: return None
    return (c>0)==home
def tot(x, over):
    if x['tl'] is None or x['tot']==x['tl']: return None
    return (x['tot']>x['tl'])==over
rows=[]
def show(name,f):
    out=[]
    for ss in ((2021,2022,2023),(2024,2025)):
        res=[v for v in (f(x) for x in R if x['s'] in ss) if v is not None]
        w=sum(res); out.append((w,len(res)-w,100*w/len(res) if res else 0))
    a,b=out; tw=a[0]+b[0]; tn=a[0]+a[1]+b[0]+b[1]
    ok = a[2]>=53 and b[2]>=53 and a[0]+a[1]>=80 and b[0]+b[1]>=60
    print(f"{name:52s} {a[0]:4d}-{a[1]:<4d} {a[2]:5.1f}% | {b[0]:4d}-{b[1]:<4d} {b[2]:5.1f}% | all {100*tw/max(tn,1):5.1f}% n={tn}{'  <== holds' if ok else ''}")
print('--- totals cutoff ---')
for c in (50,52,54,55,56,57,58,60,62,65,68):
    show(f'unders total {c}+', lambda x,c=c: tot(x,False) if x['tl'] and x['tl']>=c else None)
for lo,hi in ((54,56),(56,58),(58,62),(62,66),(66,99)):
    show(f'unders total {lo}-{hi-0.5}', lambda x,lo=lo,hi=hi: tot(x,False) if x['tl'] and lo<=x['tl']<hi else None)
print('--- 58+ refinements ---')
show('unders 58+ conference game', lambda x: tot(x,False) if x['tl'] and x['tl']>=58 and x['conf'] else None)
show('unders 58+ nonconference', lambda x: tot(x,False) if x['tl'] and x['tl']>=58 and not x['conf'] else None)
show('unders 58+ week 8+', lambda x: tot(x,False) if x['tl'] and x['tl']>=58 and x['wk']>=8 else None)
show('unders 58+ both teams off a 60+ point game', lambda x: tot(x,False) if x['tl'] and x['tl']>=58 else None)
print('--- rest ---')
show('team on short rest (<=5 days) - bet against', lambda x: (side(x,False) if (x['hrest'] or 99)<=5 and (x['arest'] or 0)>=7 else side(x,True) if (x['arest'] or 99)<=5 and (x['hrest'] or 0)>=7 else None))
show('team off bye (13+ days) vs team on normal rest', lambda x: (side(x,True) if (x['hrest'] or 0)>=13 and 6<=(x['arest'] or 0)<=8 else side(x,False) if (x['arest'] or 0)>=13 and 6<=(x['hrest'] or 0)<=8 else None))
show('unders short-week games (both <=5 days)', lambda x: tot(x,False) if (x['hrest'] or 99)<=5 and (x['arest'] or 99)<=5 else None)
print('--- look-ahead / letdown ---')
TOP=1750
show('fade favorite with big game next (next opp elo 1750+)', lambda x: (side(x,False) if x['sp']<0 and (x['hnext_elo'] or 0)>=TOP and x['ae']<TOP else side(x,True) if x['sp']>0 and (x['anext_elo'] or 0)>=TOP and x['he']<TOP else None))
show('fade team off upset win as 10+ dog', lambda x: (side(x,False) if (x['hprev_sp'] or 0)>=10 and (x['hprev_m'] or 0)>0 else side(x,True) if (x['aprev_sp'] or 0)>=10 and (x['aprev_m'] or 0)>0 else None))
show('back team off loss as 10+ favorite (bounce back)', lambda x: (side(x,True) if (x['hprev_sp'] or 0)<=-10 and (x['hprev_m'] or 0)<0 else side(x,False) if (x['aprev_sp'] or 0)<=-10 and (x['aprev_m'] or 0)<0 else None))
show('back team off a 28+ blowout loss', lambda x: (side(x,True) if (x['hprev_m'] or 0)<=-28 else side(x,False) if (x['aprev_m'] or 0)<=-28 else None))
show('fade team off a 35+ blowout win', lambda x: (side(x,False) if (x['hprev_m'] or 0)>=35 else side(x,True) if (x['aprev_m'] or 0)>=35 else None))
print('--- key numbers ---')
show('dogs getting exactly +3 / +3.5', lambda x: (side(x,True) if x['sp'] in (3,3.5) else side(x,False) if x['sp'] in (-3,-3.5) else None))
show('dogs getting +7 / +7.5', lambda x: (side(x,True) if x['sp'] in (7,7.5) else side(x,False) if x['sp'] in (-7,-7.5) else None))
show('favorites laying -2.5 or less', lambda x: (side(x,True) if -2.5<=x['sp']<0 else side(x,False) if 0<x['sp']<=2.5 else None))
