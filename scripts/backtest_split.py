#!/usr/bin/env python3
"""Backtest The Split's pick rule on past college seasons.
Input: a CSV of FBS games with closing spread/total, scores and pregame Elo (cfbfastR schedules
joined with betting lines), path as the first argument (default cfb_hist.csv). Elo stands in
for ESPN's FPI; season-to-date points for/against stand in for the stats matchup."""
import sys
import csv, collections, math
rows=[r for r in csv.DictReader(open(sys.argv[1] if len(sys.argv) > 1 else 'cfb_hist.csv'))]
def f(x):
    try: return float(x)
    except: return None
rows.sort(key=lambda r:r['start_date'])
# season-to-date points for/against per team (all games, before this one)
pf=collections.defaultdict(list); pa=collections.defaultdict(list)
data=[]
for r in rows:
    if r['completed']!='True': continue
    hp,ap=f(r['home_points']),f(r['away_points'])
    if hp is None or ap is None: continue
    s=r['season']; h=(s,r['home_id']); a=(s,r['away_id'])
    sp=f(r['home_spread']); tl=f(r['total_line']); he=f(r['home_pregame_elo']); ae=f(r['away_pregame_elo'])
    fbs = r['home_division']=='fbs' and r['away_division']=='fbs'
    if fbs and r['season_type']=='regular' and sp is not None and len(pf[h])>=3 and len(pf[a])>=3 and he and ae:
        data.append(dict(season=int(s), neutral=r['neutral_site']=='True', sp=sp, tl=tl, hp=hp, ap=ap,
            hoff=sum(pf[h])/len(pf[h]), hdef=sum(pa[h])/len(pa[h]), aoff=sum(pf[a])/len(pf[a]), adef=sum(pa[a])/len(pa[a]), elo=he-ae))
    pf[h].append(hp); pa[h].append(ap); pf[a].append(ap); pa[a].append(hp)
print("games",len(data), collections.Counter(d['season'] for d in data))
# fit elo -> points on 2015-2019
import statistics
tr=[d for d in data if d['season']<=2019]
xs=[d['elo'] for d in tr]; ys=[(d['hp']-d['ap'])-(0 if d['neutral'] else 2.5) for d in tr]
k=sum(x*y for x,y in zip(xs,ys))/sum(x*x for x in xs); print("elo points per elo point",round(k,4))
def evalrule(test, side_gap=3, tot_gap=6, mode="both"):
    w=l=tw=tl_=0
    for d in test:
        hfa=0 if d['neutral'] else 2.5
        sh=(d['hoff']+d['adef'])/2+hfa/2; sa=(d['aoff']+d['hdef'])/2-hfa/2
        sm, st = sh-sa, sh+sa
        fm = k*d['elo']+hfa
        mm=-d['sp']; real=(d['hp']-d['ap'])
        es,ef=sm-mm,fm-mm
        ok = (abs(es)>=side_gap and abs(ef)>=side_gap and es*ef>0) if mode=="both" else (abs(es)>=side_gap if mode=="stats" else abs(ef)>=side_gap)
        if ok:
            res=real-mm
            if res!=0:
                if (res>0)==((es if mode!="elo" else ef)>0): w+=1
                else: l+=1
        if d['tl'] is not None and abs(st-d['tl'])>=tot_gap:
            r2=d['hp']+d['ap']-d['tl']
            if r2!=0:
                if (r2>0)==(st>d['tl']): tw+=1
                else: tl_+=1
    return w,l,tw,tl_
test=[d for d in data if d['season']>=2020]
print("test seasons 2020-2025:",len(test))
for mode in ("both","stats","elo"):
    for g in (2,3,4,5,6,8):
        w,l,tw,tl_=evalrule(test,g,99,mode)
        print(f"side {mode:5} gap {g}: {w}-{l} = {w/max(1,w+l):.3f}  ({(w+l)/6:.0f}/season)")
for g in (4,6,8,10,12):
    _,_,tw,tl_=evalrule(test,99,g)
    print(f"total gap {g}: {tw}-{tl_} = {tw/max(1,tw+tl_):.3f} ({(tw+tl_)/6:.0f}/season)")
