"""Leave-one-template-out for the harm-label probe gate (v2fresh gate events): train on 7 templates, test on the
held-out template (unseen task type). TPR@1%FPR on the held-out template's safe actions + its hard negatives."""
import json, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from cape.activations.storage import load_activations
from cape.eval.statistics import auroc
from cape.utils.config import REPO_ROOT
G=pd.read_parquet(REPO_ROOT/"results/v3/gate_events_Qwen3.8-27B.parquet")
col=set(json.load(open(REPO_ROOT/"results/validity/identity_collisions.json"))["v2fresh"])
G=G[~G.scenario_id.isin(col)].reset_index(drop=True)
def idxmap(a):
    idx,X=load_activations(REPO_ROOT/a,"pre_action_last",[46]); return {(r.episode_id,r.event_id):X[46][int(r.row)] for r in idx.itertuples()}
mm=idxmap("outputs/activations/v2fresh_minus/L46"); pm=idxmap("outputs/activations/v2fresh_plus/L30-38-46-54-62_pre_action_last")
vecs=[(mm if r.set=="v2fresh_minus" else pm).get((r.episode_id,r.event_id)) for r in G.itertuples()]
keep=np.array([v is not None for v in vecs]); G=G[keep].reset_index(drop=True); X=np.vstack([v for v,k in zip(vecs,keep) if k])
y=G.y.values.astype(int); res={}
for t in sorted(G.template.unique()):
    te=(G.template==t).values; tr=~te
    if y[te].sum()<3: 
        res[t]={"n_harm":int(y[te].sum()),"note":"too few harms to evaluate"}; continue
    sc=StandardScaler().fit(X[tr]); lr=LogisticRegression(C=1.0,max_iter=2000,class_weight="balanced").fit(sc.transform(X[tr]),y[tr])
    s=lr.decision_function(sc.transform(X[te])); yt=y[te]; neg=(yt==0); hn=((G.hard_neg.values[te]==1)&(yt==0))
    def tpr(nm): return float((s[yt==1]>=np.quantile(s[nm],0.99)).mean()) if nm.sum()>10 else None
    def tprB(nm): b=G.B_resolved.values[te]; return float((b[yt==1]>=np.quantile(b[nm],0.99)).mean()) if nm.sum()>10 else None
    res[t]={"n_harm":int(yt.sum()),"probe_LOTO_auroc":round(float(auroc(yt,s)),4),"probe_LOTO_TPR@1%":round(tpr(neg),3),
            "probe_LOTO_TPR@1%_hardneg":(round(tpr(hn),3) if tpr(hn) is not None else None),
            "resolvedB_TPR@1%":round(tprB(neg),3)}
print(json.dumps(res,indent=1)); (REPO_ROOT/"results/authz_probe/gate_loto.json").write_text(json.dumps(res,indent=1))
