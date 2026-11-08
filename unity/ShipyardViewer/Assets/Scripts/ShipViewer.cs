using System.Collections;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using UnityEngine;

// 샘플 호선(Demo Ship 01)을 코드로 만들고 궤도 카메라와 브라우저 계약(SetView, 준비 신호)을 제공한다.
public class ShipViewer : MonoBehaviour
{
    public Camera cam;
    public Material hullLower, hullUpper, deck, house, accent, glass, steel, ground;

#if UNITY_WEBGL && !UNITY_EDITOR
    [DllImport("__Internal")] static extern void ShipViewer_NotifyReady();
#else
    static void ShipViewer_NotifyReady() { }
#endif

    const float Length = 60f, Beam = 10f, Depth = 6f, Keel = .8f, DraftSplit = 2.6f, Rake = 3f;
    const int Stations = 72;
    static readonly float[] Rows = { 0, .2f, .5f, .9f, 1.3f, 1.6f, 2.1f, 2.6f, 3.2f, 4, 5, 5.6f, 6 };
    const float DeckY = Keel + Depth;

    // 카메라 상수
    const float Damp = 12f, MinPitch = 4, MaxPitch = 88, MinDist = 50, MaxDist = 260;
    static readonly Vector3 DefaultPivot = new Vector3(0, 7, 0);
    static readonly Vector3 PivotMin = new Vector3(-10, 2, -14), PivotMax = new Vector3(10, 14, 14);

    float yaw, pitch, dist, tYaw, tPitch, tDist;
    Vector3 pivot, tPivot;
    Vector2 lastMouse;
    Mesh cube;

    void Awake()
    {
#if UNITY_WEBGL && !UNITY_EDITOR
        WebGLInput.captureAllKeyboardInput = false;
#endif
        // 기본 그림자 거리로는 궤도 거리에서 그림자가 사라진다.
        QualitySettings.shadows = ShadowQuality.All;
        QualitySettings.shadowDistance = 400;
        BuildModel();
        View("reset");
        yaw = tYaw; pitch = tPitch; dist = tDist; pivot = tPivot;
        Apply();
    }

    IEnumerator Start()
    {
        yield return new WaitForEndOfFrame();
        ShipViewer_NotifyReady();
    }

    // 브라우저: instance.SendMessage('ShipViewer','SetView',view)
    public void SetView(string view) => View(view);

    void View(string view)
    {
        float y, p, w, h;
        switch (view)
        {
            case "front": y = 180; p = 6; w = 10; h = 15; break;
            case "side": y = -90; p = 6; w = 33; h = 15; break;
            case "top": y = -90; p = 88; w = 33; h = 10; break;
            case "reset": y = -130; p = 20; w = 34; h = 15; break;
            default: return;
        }
        tYaw += Mathf.DeltaAngle(tYaw, y);
        tPitch = p;
        tPivot = DefaultPivot;
        float t = Mathf.Tan(cam.fieldOfView * .5f * Mathf.Deg2Rad);
        tDist = Mathf.Clamp(Mathf.Max(w / (t * cam.aspect), h / t) * 1.15f, MinDist, MaxDist);
    }

    void Update()
    {
        Vector2 mouse = Input.mousePosition;
        Vector2 px = Input.GetMouseButtonDown(0) || Input.GetMouseButtonDown(1) ? Vector2.zero : mouse - lastMouse;
        lastMouse = mouse;
        if (Input.GetMouseButton(0))
        {
            tYaw += px.x * .3f;
            tPitch = Mathf.Clamp(tPitch - px.y * .25f, MinPitch, MaxPitch);
        }
        else if (Input.GetMouseButton(1))
        {
            float perPx = 2 * dist * Mathf.Tan(cam.fieldOfView * .5f * Mathf.Deg2Rad) / Mathf.Max(1, Screen.height);
            Vector3 move = -(cam.transform.right * px.x + cam.transform.up * px.y) * perPx;
            tPivot = Vector3.Max(PivotMin, Vector3.Min(PivotMax, tPivot + move));
        }
        float wheel = Mathf.Clamp(Input.mouseScrollDelta.y, -3, 3);
        if (wheel != 0) tDist = Mathf.Clamp(tDist * Mathf.Exp(-wheel * .12f), MinDist, MaxDist);

        float k = 1 - Mathf.Exp(-Damp * Time.unscaledDeltaTime);
        yaw = Follow(yaw, tYaw, k);
        pitch = Follow(pitch, tPitch, k);
        dist = Follow(dist, tDist, k);
        pivot = Vector3.Distance(pivot, tPivot) < 1e-4f ? tPivot : Vector3.Lerp(pivot, tPivot, k);
        Apply();
    }

    // 목표에 충분히 가까우면 맞춰서 reset이 초기 화면과 픽셀 단위로 같게 한다.
    static float Follow(float cur, float target, float k) =>
        Mathf.Abs(target - cur) < 1e-4f ? target : Mathf.Lerp(cur, target, k);

    void Apply()
    {
        Quaternion rot = Quaternion.Euler(pitch, yaw, 0);
        cam.transform.SetPositionAndRotation(pivot - rot * Vector3.forward * dist, rot);
    }

    // ---------- 모델 ----------

    void BuildModel()
    {
        cube = CubeMesh();
        var root = new GameObject("DemoShip01").transform;
        root.SetParent(transform, false);
        Hull(root);

        // 지면, 킬 블록
        Box(root, ground, new Vector3(0, -.05f, 0), new Vector3(800, .1f, 800));
        for (int i = 0; i < 9; i++) Box(root, steel, new Vector3(0, Keel / 2, -24 + i * 6), new Vector3(1.6f, Keel, 1.2f));

        // 3단 선실 + 브리지(z≈-20)
        float y = DeckY;
        float[,] tiers = { { 9, 3, -23.6f, -14f }, { 8.6f, 2.6f, -23.4f, -15.4f }, { 8.2f, 2.6f, -23.2f, -16.6f }, { 9.4f, 1.8f, -22.6f, -17.6f } };
        for (int i = 0; i < 4; i++)
        {
            float w = tiers[i, 0], h = tiers[i, 1], z0 = tiers[i, 2], z1 = tiers[i, 3];
            Box(root, house, new Vector3(0, y + h / 2, (z0 + z1) / 2), new Vector3(w, h, z1 - z0));
            Box(root, glass, new Vector3(0, y + h * .6f, z1 + .03f), new Vector3(w * .8f, h * .22f, .08f));
            y += h;
        }
        // 브리지 윙(양현으로 뻗은 지붕)과 강재 지붕
        Box(root, house, new Vector3(0, y + .12f, -20.1f), new Vector3(12.4f, .25f, 4.4f));
        Box(root, steel, new Vector3(0, y - .9f, -20.1f), new Vector3(12f, .2f, 3.6f));
        // 오렌지 굴뚝
        Box(root, accent, new Vector3(0, DeckY + 5.2f, -25), new Vector3(2.6f, 10.4f, 2.8f));
        Box(root, steel, new Vector3(0, DeckY + 10.5f, -25), new Vector3(2.8f, .25f, 3f));
        // 마스트
        Box(root, steel, new Vector3(0, y + 1.8f, -19.6f), new Vector3(.25f, 3.4f, .25f));
        Box(root, steel, new Vector3(0, y + 2.6f, -19.6f), new Vector3(2.4f, .15f, .15f));

        // 해치 4개: 오렌지 코밍 + 강재 덮개
        for (int i = 0; i < 4; i++)
        {
            float z = -9.5f + i * 8.2f;
            Box(root, accent, new Vector3(0, DeckY + .45f, z), new Vector3(7f, .9f, 6.8f));
            Box(root, steel, new Vector3(0, DeckY + 1f, z), new Vector3(6.4f, .2f, 6.2f));
        }
        // 카고 포스트 3개와 붐
        foreach (float z in new[] { -13.6f, 2.8f, 19.2f })
        {
            Box(root, steel, new Vector3(0, DeckY + 2.6f, z), new Vector3(.7f, 5.2f, .7f));
            Box(root, steel, new Vector3(0, DeckY + 5f, z + 3.2f), new Vector3(.35f, .35f, 6f));
        }
    }

    static float HalfWidth(float z, float h)
    {
        float section = 1 - .55f * Mathf.Pow(1 - Mathf.Clamp01(h / 1.6f), 3);
        float plan = 1;
        float zs = z - Rake * (h / Depth);
        if (zs > 12) plan = 1 - Mathf.Pow(Mathf.Clamp01((zs - 12) / 15), 2.2f);
        if (z < -18)
        {
            float s = Mathf.Clamp01((-18 - z) / 12);
            plan *= 1 - .28f * s * s;
            section *= Mathf.Pow(Mathf.Clamp01((h + .15f) / 6), .7f * s);
        }
        return Beam / 2 * section * plan;
    }

    // 현측은 현별로 정점을 병합해 곡면 법선을 만들고, 바닥·갑판·선미판은 각지게 둔다.
    void Hull(Transform root)
    {
        int nr = Rows.Length, split = System.Array.IndexOf(Rows, DraftSplit);
        var grid = new Vector3[2, Stations, nr];
        for (int s = 0; s < 2; s++)
            for (int i = 0; i < Stations; i++)
            {
                float z = -Length / 2 + Length * i / (Stations - 1);
                for (int j = 0; j < nr; j++)
                    grid[s, i, j] = new Vector3((s == 0 ? -1 : 1) * HalfWidth(z, Rows[j]), Keel + Rows[j], z);
            }

        var lower = new MeshBuilder();
        var upper = new MeshBuilder();
        for (int s = 0; s < 2; s++)
        {
            var hint = new Vector3(s == 0 ? -1 : 1, 0, 0);
            int[,] idxL = new int[Stations, nr], idxU = new int[Stations, nr];
            for (int i = 0; i < Stations; i++)
                for (int j = 0; j < nr; j++)
                {
                    if (j <= split) idxL[i, j] = lower.Vertex(grid[s, i, j]);
                    if (j >= split) idxU[i, j] = upper.Vertex(grid[s, i, j]);
                }
            for (int i = 0; i < Stations - 1; i++)
                for (int j = 0; j < nr - 1; j++)
                {
                    var (mb, idx) = j < split ? (lower, idxL) : (upper, idxU);
                    mb.Quad(idx[i, j], idx[i + 1, j], idx[i + 1, j + 1], idx[i, j + 1], hint);
                }
        }
        // 바닥(아래), 갑판(위), 선미판(뒤)
        var bottom = new MeshBuilder();
        var deckMb = new MeshBuilder();
        for (int i = 0; i < Stations - 1; i++)
        {
            bottom.FlatQuad(grid[0, i, 0], grid[1, i, 0], grid[1, i + 1, 0], grid[0, i + 1, 0], Vector3.down);
            deckMb.FlatQuad(grid[0, i, nr - 1], grid[1, i, nr - 1], grid[1, i + 1, nr - 1], grid[0, i + 1, nr - 1], Vector3.up);
        }
        for (int j = 0; j < nr - 1; j++)
            (j < split ? bottom : upper).FlatQuad(grid[0, 0, j], grid[1, 0, j], grid[1, 0, j + 1], grid[0, 0, j + 1], Vector3.back);

        Part(root, "HullLower", lower.Build(), hullLower);
        Part(root, "HullUpper", upper.Build(), hullUpper);
        Part(root, "Bottom", bottom.Build(), hullLower);
        Part(root, "Deck", deckMb.Build(), deck);
    }

    void Part(Transform root, string name, Mesh mesh, Material mat)
    {
        var go = new GameObject(name);
        go.transform.SetParent(root, false);
        go.AddComponent<MeshFilter>().sharedMesh = mesh;
        go.AddComponent<MeshRenderer>().sharedMaterial = mat;
    }

    void Box(Transform root, Material mat, Vector3 center, Vector3 size)
    {
        var go = new GameObject("Box");
        go.transform.SetParent(root, false);
        go.transform.localPosition = center;
        go.transform.localScale = size;
        go.AddComponent<MeshFilter>().sharedMesh = cube;
        go.AddComponent<MeshRenderer>().sharedMaterial = mat;
    }

    // physics 모듈이 없으므로 CreatePrimitive 대신 직접 만든 단위 상자를 쓴다.
    static Mesh CubeMesh()
    {
        var mb = new MeshBuilder();
        Vector3[] n = { Vector3.right, Vector3.left, Vector3.up, Vector3.down, Vector3.forward, Vector3.back };
        foreach (var f in n)
        {
            Vector3 a = f * .5f, u = Vector3.Cross(f, Mathf.Abs(f.y) > .5f ? Vector3.forward : Vector3.up) * .5f, v = Vector3.Cross(f, u);
            mb.FlatQuad(a - u - v, a + u - v, a + u + v, a - u + v, f);
        }
        return mb.Build();
    }

    class MeshBuilder
    {
        readonly List<Vector3> verts = new List<Vector3>();
        readonly List<int> tris = new List<int>();

        public int Vertex(Vector3 p) { verts.Add(p); return verts.Count - 1; }

        // 바깥 방향 힌트로 면 방향을 정하고 0 면적 면은 건너뛴다.
        void Tri(int a, int b, int c, Vector3 hint)
        {
            Vector3 n = Vector3.Cross(verts[b] - verts[a], verts[c] - verts[a]);
            if (n.sqrMagnitude < 1e-10f) return;
            if (Vector3.Dot(n, hint) < 0) (b, c) = (c, b);
            tris.Add(a); tris.Add(b); tris.Add(c);
        }

        public void Quad(int a, int b, int c, int d, Vector3 hint)
        {
            Tri(a, b, c, hint);
            Tri(a, c, d, hint);
        }

        public void FlatQuad(Vector3 a, Vector3 b, Vector3 c, Vector3 d, Vector3 hint) =>
            Quad(Vertex(a), Vertex(b), Vertex(c), Vertex(d), hint);

        public Mesh Build()
        {
            var m = new Mesh();
            m.SetVertices(verts);
            m.SetTriangles(tris, 0);
            m.RecalculateNormals();
            m.RecalculateBounds();
            return m;
        }
    }
}
