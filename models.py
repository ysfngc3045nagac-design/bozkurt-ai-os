import math, random
from datetime import datetime
from config import VALUE_EDGE_THRESHOLD, TWIN_CETVEL_AGREEMENT_REQUIRED

def poisson_prob(lam, k):
    return (lam**k) * math.exp(-lam) / math.factorial(k)

def poisson_predict(home_xg, away_xg, max_g=6):
    hw=dr=aw=0.0; best_p=0; best_s="1-1"
    for i in range(max_g+1):
        for j in range(max_g+1):
            p=poisson_prob(home_xg,i)*poisson_prob(away_xg,j)
            if p>best_p: best_p=p; best_s=f"{i}-{j}"
            if i>j: hw+=p
            elif i==j: dr+=p
            else: aw+=p
    return {"home":round(hw*100,1),"draw":round(dr*100,1),"away":round(aw*100,1),"score":best_s,"conf":round(best_p*100,2)}

def elo_predict(h_elo, a_elo, home_adv=53):
    h=1/(1+10**((a_elo-(h_elo+home_adv))/400))
    a=1/(1+10**((h_elo+home_adv-a_elo)/400))
    d=max(0.10,min(0.28,1-h-a)); t=h+a+d
    return {"home":round(h/t*(1-d)*100,1),"draw":round(d*100,1),"away":round(a/t*(1-d)*100,1)}

def kelly(odds, prob, bankroll=1000, frac=4):
    b=odds-1; q=1-prob
    f=max(0,(b*prob-q)/b) if b>0 else 0
    stake=min((f/frac)*bankroll, bankroll*0.05)
    return {"stake":round(stake,2),"kelly_pct":round(f*100,2),"rec":"YAP" if f>0.02 else "YAPMA"}

def novig(h,d,a):
    inv=1/h+1/d+1/a
    return {"home":round(1/h/inv*100,1),"draw":round(1/d/inv*100,1),"away":round(1/a/inv*100,1),"margin":round((inv-1)*100,2)}

def monte_carlo(h_xg, a_xg, n=3000):
    hw=dr=aw=0
    for _ in range(n):
        hg=random.choices(range(7),[poisson_prob(h_xg,k) for k in range(7)])[0]
        ag=random.choices(range(7),[poisson_prob(a_xg,k) for k in range(7)])[0]
        if hg>ag: hw+=1
        elif hg==ag: dr+=1
        else: aw+=1
    return {"home":round(hw/n*100,1),"draw":round(dr/n*100,1),"away":round(aw/n*100,1)}

def asian_handicap(h_elo, a_elo, h_xg, a_xg):
    ed=h_elo-a_elo; xd=h_xg-a_xg
    if ed>200 and xd>0.5: line=-1.5
    elif ed>100 and xd>0.3: line=-1.0
    elif ed>50: line=-0.5
    elif ed<-200 and xd<-0.5: line=1.5
    elif ed<-100 and xd<-0.3: line=1.0
    elif ed<-50: line=0.5
    else: line=0.0
    return {"line":line,"rec":f"Ev {line:+.1f}" if line!=0 else "Handicap yok"}

def btts_calc(h_xg, a_xg, h_xga, a_xga):
    p=(h_xg/(h_xg+a_xga))*(a_xg/(a_xg+h_xga))
    return {"yes":round(p*100,1),"no":round((1-p)*100,1),"rec":"KG VAR" if p>0.55 else "KG YOK" if p<0.45 else "BELİRSİZ"}

def over_under_calc(h_xg, a_xg):
    p=1-sum(poisson_prob(h_xg,i)*poisson_prob(a_xg,j) for i in range(3) for j in range(3-i))
    return {"over":round(p*100,1),"under":round((1-p)*100,1),"rec":"ÜST 2.5" if p>0.55 else "ALT 2.5" if p<0.45 else "BELİRSİZ"}

def corner_calc(h_xg, a_xg):
    t=h_xg*3.2+a_xg*2.8
    return {"total":round(t,1),"rec":"ÜST 9.5" if t>10 else "ALT 9.5" if t<8 else "BELİRSİZ"}

def value_bet_check(model_prob, novig_prob, threshold=VALUE_EDGE_THRESHOLD):
    return model_prob > novig_prob + threshold

def twin_cetvel(home, away):
    results={}
    params=[
        ("ELO",home["elo"],away["elo"],True),
        ("Sıralama",home["rank"],away["rank"],False),
        ("Puan",home["points"],away["points"],True),
        ("Değer (M€)",home["value"],away["value"],True),
        ("xG",home["xg"],away["xg"],True),
        ("xGA",home["xga"],away["xga"],False),
        ("Gol Farkı",home["goals_for"]-home["goals_against"],away["goals_for"]-away["goals_against"],True),
        ("Ev/Dep Puan",home["home_points"],away["away_points"],True),
    ]
    hfp=sum(3 if r=="W" else 1 if r=="D" else 0 for r in home["form"][:5])
    afp=sum(3 if r=="W" else 1 if r=="D" else 0 for r in away["form"][:5])
    params.append(("Form",hfp,afp,True))
    hw=aw=0
    for name,hv,av,higher in params:
        if higher: winner="home" if hv>av else "away" if av>hv else "draw"
        else: winner="home" if hv<av else "away" if av<hv else "draw"
        results[name]={"home":hv,"away":av,"winner":winner}
        if winner=="home": hw+=1
        elif winner=="away": aw+=1
    results["ÖZET"]={"home_wins":hw,"away_wins":aw,"winner":"home" if hw>aw else "away" if aw>hw else "draw"}
    return results

def apply_filters(home, away, match_data):
    filters=[]; md=match_data or {}
    def f(name,score,desc,impact): filters.append({"name":name,"score":score,"desc":desc,"impact":impact})
    sc=7 if home.get("style")!=away.get("style") else 5
    f("Stil",sc,"Stil analizi","neutral")
    hm=home.get("injuries",0)+home.get("suspensions",0)
    am=away.get("injuries",0)+away.get("suspensions",0)
    f("Kadro",3 if hm>=3 else 8 if am>=3 else 6,f"Ev {hm} eksik, Dep {am} eksik","negative" if hm>=3 else "positive" if am>=3 else "neutral")
    cards=md.get("referee_cards",3.5)
    f("Hakem",7 if cards>4.5 else 5 if cards<3 else 6,f"Kart ort: {cards}","neutral")
    cond=md.get("weather","Güneşli"); temp=md.get("temp",18)
    f("Hava",5 if cond in ["Yağmurlu","Karlı"] else 4 if temp>32 or temp<0 else 7,f"{cond} {temp}°C","neutral")
    is_d=md.get("is_derby",False)
    f("Derbi",2 if is_d else 8,"Derbi maçı!" if is_d else "Normal maç","negative" if is_d else "positive")
    mov=abs(md.get("odds_movement",0))
    f("Para Akışı",6 if mov>10 else 7,f"Oran hareketi: %{mov}","neutral")
    hour=md.get("hour",15)
    f("Saat",5 if hour in [12,13] or hour>=21 else 7,f"Saat {hour}:00","neutral")
    cap=home.get("stadium_capacity",30000)
    f("Taraftar",8 if cap>50000 else 5 if cap<15000 else 6,f"Stadyum {cap:,}","neutral")
    hd=home.get("squad_depth",5); ad=away.get("squad_depth",5)
    f("Kadro Derinliği",8 if hd>=8 and ad<6 else 3 if ad>=8 and hd<6 else 6,f"Ev:{hd} Dep:{ad}","neutral")
    h3=sum(home.get("last5_xg",[1.2]*5)[:3])/3
    a3=sum(away.get("last5_xg",[1.2]*5)[:3])/3
    f("Son 3 Maç",8 if h3>1.5 else 3 if a3>1.5 else 6,f"Ev xG:{h3:.2f} Dep xG:{a3:.2f}","neutral")
    hw2=md.get("h2h_home_wins",0); ht=md.get("h2h_total",5)
    r=hw2/ht if ht>0 else 0.5
    f("H2H",8 if r>0.7 else 3 if r<0.3 else 6,f"H2H: {hw2}/{ht}","neutral")
    hn=home.get("new_players",0); an=away.get("new_players",0)
    f("Transfer",4 if hn>=3 else 7 if an>=3 else 7,f"Ev:{hn} Dep:{an} yeni","neutral")
    hf=home.get("matches_last7",2); af=away.get("matches_last7",2)
    f("Yoğunluk",3 if hf>=3 else 8 if af>=3 else 7,f"7 günde Ev:{hf} Dep:{af} maç","neutral")
    hu=home.get("uefa_match_in_3days",False); au=away.get("uefa_match_in_3days",False)
    f("UEFA",3 if hu and not au else 8 if au and not hu else 7,"UEFA etkisi","neutral")
    hi=home.get("international_players",0); ai=away.get("international_players",0)
    f("Milli Ara",4 if hi>5 and ai<3 else 7 if ai>5 and hi<3 else 6,f"Ev:{hi} Dep:{ai} milli","neutral")
    hc=home.get("cup_match_in_3days",False); ac=away.get("cup_match_in_3days",False)
    f("Kupa",4 if hc and not ac else 7 if ac and not hc else 6,"Kupa etkisi","neutral")
    month=md.get("month",datetime.now().month)
    f("Sezon",5 if month in [8,9] else 4 if month in [12,1] else 8 if month in [10,11] else 6,f"Ay: {month}","neutral")
    pitch=md.get("pitch_type","doğal")
    f("Zemin",5 if pitch=="suni" else 4 if pitch=="çamur" else 7,f"Zemin: {pitch}","neutral")
    dist=md.get("travel_distance",0)
    f("Seyahat",4 if dist>1000 else 5 if dist>500 else 7,f"{dist}km","neutral")
    hme=home.get("manager_exp",5); ame=away.get("manager_exp",5)
    f("TD",8 if hme>15 else 3 if ame>15 else 6,f"Ev:{hme}y Dep:{ame}y tecrübe","neutral")
    hn2=home.get("news_factor",0); an2=away.get("news_factor",0)
    f("Haberler",3 if hn2<-20 else 8 if an2<-20 else 6,"Haber akışı","neutral")
    total=sum(x["score"] for x in filters)
    pct=round(total/(len(filters)*10)*100,1)
    return filters, pct, pct>=60

def master_analyze(home, away, odds, match_data=None, bankroll=1000):
    md=match_data or {}
    h_xg=(home["xg"]*away["xga"])/1.4
    a_xg=(away["xg"]*home["xga"])/1.4
    pois=poisson_predict(h_xg,a_xg)
    elo=elo_predict(home["elo"],away["elo"])
    mc=monte_carlo(h_xg,a_xg)
    nv=novig(odds["home"],odds["draw"],odds["away"])
    ah=asian_handicap(home["elo"],away["elo"],h_xg,a_xg)
    btts=btts_calc(h_xg,a_xg,home["xga"],away["xga"])
    ou=over_under_calc(h_xg,a_xg)
    corn=corner_calc(h_xg,a_xg)
    twin=twin_cetvel(home,away)
    filts,filt_pct,filt_pass=apply_filters(home,away,md)
    twin_winner=twin["ÖZET"]["winner"]
    twin_bonus=5 if twin_winner=="home" else -5 if twin_winner=="away" else 0
    ph=(0.30*elo["home"]+0.25*pois["home"]+0.20*mc["home"]+0.15*(filt_pct*0.6)+0.10*(50+twin_bonus))/100
    pa=(0.30*elo["away"]+0.25*pois["away"]+0.20*mc["away"]+0.15*(filt_pct*0.4)+0.10*(50-twin_bonus))/100
    pd=max(0.08,min(0.28,1-ph-pa))
    t=ph+pd+pa; ph,pa=ph/t*(1-pd),pa/t*(1-pd)
    vb=None
    ev_h=round((ph*(odds["home"]-1)-(1-ph))*100,2)
    ev_d=round((pd*(odds["draw"]-1)-(1-pd))*100,2)
    ev_a=round((pa*(odds["away"]-1)-(1-pa))*100,2)
    candidates=[]
    if value_bet_check(ph*100,nv["home"]): candidates.append(("Ev","home"))
    if value_bet_check(pd*100,nv["draw"]): candidates.append(("Beraberlik","draw"))
    if value_bet_check(pa*100,nv["away"]): candidates.append(("Deplasman","away"))
    if candidates and TWIN_CETVEL_AGREEMENT_REQUIRED:
        filtered=[]
        for label,side in candidates:
            if side=="home" and twin_winner=="home": filtered.append((label,side))
            elif side=="away" and twin_winner=="away": filtered.append((label,side))
            elif side=="draw": filtered.append((label,side))
        candidates=filtered
    if candidates: vb=candidates[0][0]
    k=kelly(odds["home"] if vb=="Ev" else odds["draw"] if vb=="Beraberlik" else odds["away"],
            ph if vb=="Ev" else pd if vb=="Beraberlik" else pa, bankroll)
    conf=max(ph,pd,pa)*100
    if vb and k["stake"]>0:
        rec=f"✅ {vb} | Kelly: {k['stake']:.2f}TL | EV: {max(ev_h,ev_d,ev_a):+.2f}%"
    else:
        rec="❌ Value Bet yok"
    return {
        "home_prob":round(ph*100,1),"draw_prob":round(pd*100,1),"away_prob":round(pa*100,1),
        "score":pois["score"],"confidence":round(conf,1),
        "value_bet":vb,"kelly_stake":k["stake"],"recommendation":rec,
        "ev_home":ev_h,"ev_draw":ev_d,"ev_away":ev_a,
        "poisson":pois,"elo":elo,"monte_carlo":mc,
        "novig":nv,"overround_margin":nv["margin"],
        "asian_handicap":ah,"btts":btts,"over_under":ou,"corners":corn,
        "twin_cetvel":twin,"filters":filts,"filter_pct":filt_pct,"filter_passed":filt_pass,
        "h_xg":round(h_xg,2),"a_xg":round(a_xg,2),
    }

print("✅ models.py hazır!")