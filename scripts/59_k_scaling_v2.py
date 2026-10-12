"""Preliminary diversity scaling on v2fresh (8 templates): held-out-template AUROC of the unsafe-world probe vs
number of training templates K (matched x+/x- training), averaged over random subsets; fit err(K)=a+b/sqrt(K)."""
import json, itertools, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from cape.activations.storage import load_activations
from cape.eval.statistics import auroc
from cape.utils.config import REPO_ROOT
import importlib.util
s=importlib.util.spec_from_file_location("c","scripts/58_confound_test.py")
src=open("scripts/58_confound_test.py").read().split("def lr_fit")[0]   # reuse data loading only
ns={}; exec(src,ns); X,T,Y=ns["X"],ns["T"],ns["Y"]
temps=sorted(set(T)); rng=np.random.default_rng(0); out={}
for K in range(1,len(temps)):
    vals=[]
    for t in temps:
        others=[o for o in temps if o!=t]; combos=list(itertools.combinations(others,K)); rng.shuffle(combos)
        for c in combos[:4]:
            tr=np.isin(T,list(c)); te=T==t
            if len(set(Y[tr]))<2: continue
            sc=StandardScaler().fit(X[tr]); pca=PCA(min(256,int(tr.sum())-1),random_state=0).fit(sc.transform(X[tr]))   # fit on TRAIN only
            m=LogisticRegression(C=1.0,max_iter=2000,class_weight="balanced").fit(pca.transform(sc.transform(X[tr])),Y[tr])
            vals.append(auroc(Y[te],m.decision_function(pca.transform(sc.transform(X[te])))))
    out[K]={"mean_auroc":round(float(np.mean(vals)),4),"sd":round(float(np.std(vals)),4),"n":len(vals)}
Ks=np.array(list(out)); err=np.array([1-out[k]["mean_auroc"] for k in Ks])
A=np.vstack([np.ones_like(Ks,dtype=float),1/np.sqrt(Ks)]).T; coef,*_=np.linalg.lstsq(A,err,rcond=None)
pred=A@coef; r2=1-np.sum((err-pred)**2)/np.sum((err-err.mean())**2)
res={"by_K":out,"fit_err=a+b/sqrtK":{"a(asymptote_err)":round(float(coef[0]),4),"b":round(float(coef[1]),4),"R2":round(float(r2),4)}}
print(json.dumps(res,indent=1)); (REPO_ROOT/"results/authz_probe/k_scaling_v2.json").write_text(json.dumps(res,indent=1))
