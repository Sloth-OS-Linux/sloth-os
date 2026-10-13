import sys, numpy as np, cv2
src, out, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
a = cv2.imread(src, cv2.IMREAD_UNCHANGED)[:,:,3]
m = (a > 128).astype(np.uint8)*255
# A teljes logó sziluettje: a darabokat összezárjuk, a lyukakat kitöltjük
k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (91,91))
sil = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k)
cs,_ = cv2.findContours(sil, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
c = max(cs, key=cv2.contourArea)[:,0,:].astype(np.float64)
# simítás (körkörös mozgóátlag), hogy a pont ne rángasson a szőrtincseken
w = 71; pad = np.vstack([c[-w:], c, c[:w]])
ker = np.ones(w)/w
sm = np.stack([np.convolve(pad[:,i], ker, 'same')[w:-w] for i in (0,1)], 1)
# kifelé tolás pár pixellel, hogy a pont a szélen fusson, ne a formán belül
cx, cy = sm.mean(0)
# irány: óramutató járása (képkoordinátákban y lefelé nő -> pozitív előjelű terület = óramutató)
area = 0.5*np.sum(sm[:,0]*np.roll(sm[:,1],-1) - np.roll(sm[:,0],-1)*sm[:,1])
if area < 0: sm = sm[::-1]
# kezdőpont: a legfelső pont
start = np.argmin(sm[:,1]); sm = np.roll(sm, -start, 0)
# egyenletes mintavétel ívhossz szerint
seg = np.linalg.norm(np.diff(np.vstack([sm, sm[:1]]), axis=0), axis=1)
cum = np.concatenate([[0], np.cumsum(seg)]); L = cum[-1]
ts = np.linspace(0, L, N, endpoint=False)
ext = np.vstack([sm, sm[:1]])
pts = np.stack([np.interp(ts, cum, ext[:,0]), np.interp(ts, cum, ext[:,1])], 1)
# kifelé 1.2% -kal
v = pts - [cx, cy]; pts = pts + v/np.linalg.norm(v,axis=1,keepdims=True)*12
H, W = a.shape
np.savetxt(out+"/points.txt", pts/[W,H], fmt="%.4f")
# előnézet
img = cv2.imread(src, cv2.IMREAD_UNCHANGED)
bg = np.full((H,W,3), (33,30,28), np.uint8)
al = img[:,:,3:4]/255.0; bg = (img[:,:,:3]*al + bg*(1-al)).astype(np.uint8)
for i,(x,y) in enumerate(pts):
    col = (90,200,90) if i < 10 else (80,80,255)
    cv2.circle(bg, (int(x),int(y)), 4, col, -1)
cv2.circle(bg, (int(pts[0][0]),int(pts[0][1])), 14, (255,255,255), -1)
cv2.circle(bg, (int(pts[N//8][0]),int(pts[N//8][1])), 10, (0,215,255), -1)
cv2.imwrite(out+"/contour_preview.png", cv2.resize(bg, (600,600)))
print("pontok:", N, "kerület px:", int(L), "terület előjel:", area>0)
