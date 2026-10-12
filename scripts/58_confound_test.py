"""Mechanism test for the counterfactual-invariance claim. Target: unsafe-world (x- vs x+) at the first decision after
reveal. For each held-out template: (a) MATCHED training on all other templates (both x+ and x- from each template),
(b) CONFOUNDED training: other templates split in two halves, x- only from half A and x+ only from half B (label
confounded with template group), (c) difference-of-means (DoM) direction on matched data. Held-out AUROC. 10 random
splits for (b)."""
import json, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from cape.activations.storage import load_activations
from cape.eval.statistics import auroc
from cape.utils.config import REPO_ROOT
col=set(json.load(open(REPO_ROOT/"results/validity/identity_collisions.json"))["v2fresh"])
def rows(stem,cf):
    eps=pd.read_parquet(REPO_ROOT/f"outputs/rollouts/{stem}.parquet"); eps=eps[eps.cf_value==cf]; out=[]
    for ep in eps.itertuples():
        if ep.scenario_id in col: continue
        rv=ep.reveal_event
        if rv!=rv or rv is None: continue
        ev=[e for e in ep.events if e["event_id"]>int(rv) and e["action_start_pos"] is not None]
        if ev: out.append((ep.episode_id,ev[0]["event_id"],ep.template,int(cf=="unsafe")))
    return out
def load(a,keys):
    idx,X=load_activations(REPO_ROOT/a,"pre_action_last",[46]); m={(r.episode_id,r.event_id):int(r.row) for r in idx.itertuples()}
    return [(X[46][m[(e,ev)]],t,y) for e,ev,t,y in keys if (e,ev) in m]
D=load("outputs/activations/v2fresh_plus/L30-38-46-54-62_pre_action_last",rows("v2fresh_plus","safe"))+load("outputs/activations/v2fresh_minus/L46",rows("v2fresh_minus","unsafe"))
X=np.vstack([d[0] for d in D]); T=np.array([d[1] for d in D]); Y=np.array([d[2] for d in D])
def lr_fit(Xa,ya):
    sc=StandardScaler().fit(Xa); m=LogisticRegression(C=1.0,max_iter=2000,class_weight="balanced").fit(sc.transform(Xa),ya); return lambda Z: m.decision_function(sc.transform(Z))
res={}; rng=np.random.default_rng(0)
for t in sorted(set(T)):
    te=T==t; others=sorted(set(T)-{t})
    matched=lr_fit(X[~te],Y[~te]); a_m=auroc(Y[te],matched(X[te]))
    mu1=X[(~te)&(Y==1)].mean(0); mu0=X[(~te)&(Y==0)].mean(0); a_dom=auroc(Y[te],X[te]@(mu1-mu0))
    conf=[]
    for s in range(10):
        p=rng.permutation(others); A=set(p[:len(p)//2]); B=set(p[len(p)//2:])
        tr=((np.isin(T,list(A)))&(Y==1))|((np.isin(T,list(B)))&(Y==0))
        conf.append(auroc(Y[te],lr_fit(X[tr],Y[tr])(X[te])))
    res[t]={"matched_LR":round(float(a_m),3),"matched_DoM":round(float(a_dom),3),"confounded_LR_mean":round(float(np.mean(conf)),3),"confounded_LR_min":round(float(np.min(conf)),3)}
res["MEAN"]={k:round(float(np.mean([v[k] for v in res.values()])),3) for k in ("matched_LR","matched_DoM","confounded_LR_mean")}
print(json.dumps(res,indent=1)); (REPO_ROOT/"results/authz_probe/confound_test.json").write_text(json.dumps(res,indent=1))
