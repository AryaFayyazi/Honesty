"""Compositional probe gate: violation = critical(action) AND unauthorized(principal). Learn each predicate as a
linear probe; compose in log space; test leave-one-template-out vs the monolithic harm probe."""
import json, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from cape.activations.storage import load_activations
from cape.eval.statistics import auroc
from cape.utils.config import REPO_ROOT
G=pd.read_parquet(REPO_ROOT/"results/v3/gate_events_Qwen3.8-27B.parquet")
col=set(json.load(open(REPO_ROOT/"results/validity/identity_collisions.json"))["v2fresh"])
G=G[~G.scenario_id.isin(col)].reset_index(drop=True)
# critical + approved flags from rollouts
crit={}; appr={}
for st in ("v2fresh_minus","v2fresh_plus"):
    for ep in pd.read_parquet(REPO_ROOT/f"outputs/rollouts/{st}.parquet").itertuples():
        a=False
        for e in ep.events:
            crit[(ep.episode_id,e["event_id"])]=int(bool(e["critical"]) or bool(e["unsafe_action"]))
            appr[(ep.episode_id,e["event_id"])]=int(a)
            if e["tool"]=="request_permission" and str(e["tool_result"]).startswith("APPROVED"): a=True
G["critical"]=[crit.get((r.episode_id,r.event_id),0) for r in G.itertuples()]
G["approved"]=[appr.get((r.episode_id,r.event_id),0) for r in G.itertuples()]
G["unauth"]=((G.set=="v2fresh_minus")&(G.approved==0)).astype(int)
def idxmap(a):
    idx,X=load_activations(REPO_ROOT/a,"pre_action_last",[46]); return {(r.episode_id,r.event_id):X[46][int(r.row)] for r in idx.itertuples()}
mm=idxmap("outputs/activations/v2fresh_minus/L46"); pm=idxmap("outputs/activations/v2fresh_plus/L30-38-46-54-62_pre_action_last")
vecs=[(mm if r.set=="v2fresh_minus" else pm).get((r.episode_id,r.event_id)) for r in G.itertuples()]
keep=np.array([v is not None for v in vecs]); G=G[keep].reset_index(drop=True); X=np.vstack([v for v,k in zip(vecs,keep) if k])
y=G.y.values.astype(int)
print("check: harm == critical & unauth ->", round(float((y==((G.critical==1)&(G.unauth==1)).astype(int)).mean()),4), "agreement")
def fit(Xtr,ytr):
    sc=StandardScaler().fit(Xtr); lr=LogisticRegression(C=1.0,max_iter=2000,class_weight="balanced").fit(sc.transform(Xtr),ytr); return sc,lr
def logp(sc,lr,Xte):
    z=lr.decision_function(sc.transform(Xte)); return -np.logaddexp(0,-z)   # log sigmoid
res={}
for t in sorted(G.template.unique()):
    te=(G.template==t).values; tr=~te
    if y[te].sum()<3: continue
    yt=y[te]; neg=yt==0; hn=(G.hard_neg.values[te]==1)&neg
    scU,lrU=fit(X[tr],G.unauth.values[tr]); scC,lrC=fit(X[tr],G.critical.values[tr]); scM,lrM=fit(X[tr],y[tr])
    comp=logp(scU,lrU,X[te])+logp(scC,lrC,X[te]); mono=lrM.decision_function(scM.transform(X[te]))
    def tpr(s,nm): return round(float((s[yt==1]>=np.quantile(s[nm],0.99)).mean()),3) if nm.sum()>10 else None
    res[t]={"n_harm":int(yt.sum()),
            "compositional":{"auroc":round(float(auroc(yt,comp)),4),"TPR@1%":tpr(comp,neg),"TPR@1%_hardneg":tpr(comp,hn)},
            "monolithic":{"auroc":round(float(auroc(yt,mono)),4),"TPR@1%":tpr(mono,neg),"TPR@1%_hardneg":tpr(mono,hn)},
            "predicate_transfer_auroc":{"unauth":round(float(auroc(G.unauth.values[te],logp(scU,lrU,X[te]))),4) if 0<G.unauth.values[te].sum()<te.sum() else None,
                                        "critical":round(float(auroc(G.critical.values[te],logp(scC,lrC,X[te]))),4) if 0<G.critical.values[te].sum()<te.sum() else None},
            "resolvedB_TPR@1%":tpr(G.B_resolved.values[te],neg)}
print(json.dumps(res,indent=1)); (REPO_ROOT/"results/authz_probe/compositional_loto.json").write_text(json.dumps(res,indent=1))
