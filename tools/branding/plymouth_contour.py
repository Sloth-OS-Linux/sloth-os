import sys, numpy as np, cv2
src, out, N = sys.argv[1], sys.argv[2], int(sys.argv[3])
a = cv2.imread(src, cv2.IMREAD_UNCHANGED)[:,:,3]
m = (a > 128).astype(np.uint8)*255
# The silhouette of the whole logo: the pieces are closed together, the holes filled
k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (91,91))
sil = cv2.morphologyEx(m, cv2.MORPH_CLOSE, k)
cs,_ = cv2.findContours(sil, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
c = max(cs, key=cv2.contourArea)[:,0,:].astype(np.float64)
# smoothing (circular moving average), so the dot does not jerk on the tufts of fur
w = 71; pad = np.vstack([c[-w:], c, c[:w]])
ker = np.ones(w)/w
sm = np.stack([np.convolve(pad[:,i], ker, 'same')[w:-w] for i in (0,1)], 1)
# pushing outwards by a few pixels, so the dot runs on the edge, not inside the shape
cx, cy = sm.mean(0)
# direction: clockwise (in image coordinates y grows downwards -> positive signed area = clockwise)
area = 0.5*np.sum(sm[:,0]*np.roll(sm[:,1],-1) - np.roll(sm[:,0],-1)*sm[:,1])
if area < 0: sm = sm[::-1]
# starting point: the topmost point
start = np.argmin(sm[:,1]); sm = np.roll(sm, -start, 0)
# even sampling by arc length
seg = np.linalg.norm(np.diff(np.vstack([sm, sm[:1]]), axis=0), axis=1)
cum = np.concatenate([[0], np.cumsum(seg)]); L = cum[-1]
ts = np.linspace(0, L, N, endpoint=False)
ext = np.vstack([sm, sm[:1]])
pts = np.stack([np.interp(ts, cum, ext[:,0]), np.interp(ts, cum, ext[:,1])], 1)
# outwards by 1.2%
v = pts - [cx, cy]; pts = pts + v/np.linalg.norm(v,axis=1,keepdims=True)*12
H, W = a.shape
np.savetxt(out+"/points.txt", pts/[W,H], fmt="%.4f")
# preview
img = cv2.imread(src, cv2.IMREAD_UNCHANGED)
bg = np.full((H,W,3), (33,30,28), np.uint8)
al = img[:,:,3:4]/255.0; bg = (img[:,:,:3]*al + bg*(1-al)).astype(np.uint8)
for i,(x,y) in enumerate(pts):
    col = (90,200,90) if i < 10 else (80,80,255)
    cv2.circle(bg, (int(x),int(y)), 4, col, -1)
cv2.circle(bg, (int(pts[0][0]),int(pts[0][1])), 14, (255,255,255), -1)
cv2.circle(bg, (int(pts[N//8][0]),int(pts[N//8][1])), 10, (0,215,255), -1)
cv2.imwrite(out+"/contour_preview.png", cv2.resize(bg, (600,600)))
print("points:", N, "perimeter px:", int(L), "area sign:", area>0)
