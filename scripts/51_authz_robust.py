import json, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
from cape.activations.storage import load_activations
from cape.eval.statistics import auroc
from cape.utils.config import REPO_ROOT
col=set(json.load(open(REPO_ROOT/"results/validity/identity_collisions.json"))["v2fresh"])
def rows(stem,cf):
    eps=pd.read_parquet(REPO_ROOT/f"outputs/rollouts/{stem}.parquet"); eps=eps[eps.cf_value==cf]
    out=[]
    for ep in eps.itertuples():
        if ep.scenario_id in col: continue
        rv=ep.reveal_event
        if rv!=rv or rv is None: continue
        ev=[e for e in ep.events if e["event_id"]>int(rv) and e["action_start_pos"] is not None]
        if not ev: continue
        c=ev[0]
        out.append({"episode_id":ep.episode_id,"event_id":c["event_id"],"scenario_id":ep.scenario_id,
                    "template":ep.template,"y":int(cf=="unsafe")})
    return pd.DataFrame(out)
P=rows("v2fresh_plus","safe"); M=rows("v2fresh_minus","unsafe")
D=pd.concat([P,M],ignore_index=True)
def load(actdir,keys):
    idx,X=load_activations(REPO_ROOT/actdir,"pre_action_last",[46]); m={(r.episode_id,r.event_id):int(r.row) for r in idx.itertuples()}
    F=[];ok=[]
    for e,ev in keys:
        if (e,ev) in m: F.append(X[46][m[(e,ev)]]);ok.append(True)
        else: ok.append(False)
    return np.array(F),np.array(ok)
kp=list(zip(P.episode_id,P.event_id)); km=list(zip(M.episode_id,M.event_id))
Xp,okp=load("outputs/activations/v2fresh_plus/L30-38-46-54-62_pre_action_last",kp)
Xm,okm=load("outputs/activations/v2fresh_minus/L46",km)
Xf=np.vstack([Xp,Xm]); y=np.array([0]*okp.sum()+[1]*okm.sum())
g=np.array(list(P.scenario_id[okp])+list(M.scenario_id[okm])); tm=np.array(list(P.template[okp])+list(M.template[okm]))
def cv(Xf,y,g,seeds=3):
    s=np.zeros(len(y))
    for si in range(seeds):
        p=np.zeros(len(y))
        for tr,te in GroupKFold(5).split(Xf,y,g):
            sc=StandardScaler().fit(Xf[tr]); lr=LogisticRegression(C=1.0,max_iter=1500,class_weight="balanced").fit(sc.transform(Xf[tr]),y[tr]); p[te]=lr.decision_function(sc.transform(Xf[te]))
        s+=p
    return s/seeds
s=cv(Xf,y,g)
rng=np.random.default_rng(0); gl=pd.Series(range(len(g))).groupby(list(g)).apply(lambda x:x.values); gk=list(gl.index)
bs=[]
for _ in range(2000):
    pick=np.concatenate([gl[gk[i]] for i in rng.integers(0,len(gk),len(gk))]); yy=y[pick]
    if 0<yy.sum()<len(yy): bs.append(auroc(yy,s[pick]))
tt={}
for t in pd.unique(tm):
    tr=tm!=t; te=tm==t
    if 0<y[te].sum()<te.sum() and y[tr].sum()>0 and (1-y[tr]).sum()>0:
        sc=StandardScaler().fit(Xf[tr]); lr=LogisticRegression(C=1.0,max_iter=1500,class_weight="balanced").fit(sc.transform(Xf[tr]),y[tr])
        tt[t]={"n":int(te.sum()),"n_unauth":int(y[te].sum()),"auroc":round(float(auroc(y[te],lr.decision_function(sc.transform(Xf[te])))),4)}
res={"design":"first decision AFTER reveal, all episodes (balanced)","n_plus":int(okp.sum()),"n_minus":int(okm.sum()),
 "grouped_cv_auroc":round(float(auroc(y,s)),4),"ci95":[round(float(np.quantile(bs,.025)),4),round(float(np.quantile(bs,.975)),4)],
 "template_transfer_auroc":tt,"template_transfer_mean":round(float(np.mean([v["auroc"] for v in tt.values()])),4)}
print(json.dumps(res,indent=1)); (REPO_ROOT/"results/authz_probe/robust.json").write_text(json.dumps(res,indent=1))
