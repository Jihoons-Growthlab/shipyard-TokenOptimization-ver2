using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build;
using UnityEditor.Build.Reporting;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

// 씬과 재질을 매번 재생성하고 Web 빌드까지 수행한다.
// Unity -batchmode -quit -buildTarget WebGL -projectPath unity/ShipyardViewer -executeMethod ShipBuilder.Build
public static class ShipBuilder
{
    const string MatDir = "Assets/Materials";
    const string ScenePath = "Assets/Scenes/Main.unity";
    const string OutDir = "../../frontend/public/unity/ship-viewer";

    static Material Mat(string name, string hex, float smoothness)
    {
        string path = $"{MatDir}/{name}.mat";
        AssetDatabase.DeleteAsset(path);
        ColorUtility.TryParseHtmlString(hex, out Color c);
        var m = new Material(Shader.Find("Standard")) { name = name, color = c };
        m.SetFloat("_Glossiness", smoothness);
        AssetDatabase.CreateAsset(m, path);
        return m;
    }

    static void Settings()
    {
        PlayerSettings.companyName = "SWP";
        PlayerSettings.productName = "ShipyardViewer";
        PlayerSettings.colorSpace = ColorSpace.Linear;
        PlayerSettings.runInBackground = true;
        PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Disabled;
        PlayerSettings.WebGL.decompressionFallback = false;
        PlayerSettings.WebGL.nameFilesAsHashes = false;
        PlayerSettings.WebGL.dataCaching = false;
        PlayerSettings.WebGL.exceptionSupport = WebGLExceptionSupport.None;
        PlayerSettings.WebGL.template = "APPLICATION:Minimal";
        PlayerSettings.stripEngineCode = true;
        PlayerSettings.SetManagedStrippingLevel(NamedBuildTarget.WebGL, ManagedStrippingLevel.High);
        PlayerSettings.SetUseDefaultGraphicsAPIs(BuildTarget.WebGL, false);
        PlayerSettings.SetGraphicsAPIs(BuildTarget.WebGL, new[] { GraphicsDeviceType.OpenGLES3 });
    }

    static void Scene()
    {
        Directory.CreateDirectory(MatDir);
        Directory.CreateDirectory(Path.GetDirectoryName(ScenePath));
        AssetDatabase.Refresh();

        var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

        var camGo = new GameObject("Main Camera") { tag = "MainCamera" };
        var cam = camGo.AddComponent<Camera>();
        cam.clearFlags = CameraClearFlags.SolidColor;
        ColorUtility.TryParseHtmlString("#DDE4EE", out Color bg);
        cam.backgroundColor = bg;
        cam.fieldOfView = 30;
        cam.nearClipPlane = 1;
        cam.farClipPlane = 1000;

        var sun = new GameObject("Sun").AddComponent<Light>();
        sun.type = LightType.Directional;
        sun.intensity = .95f;
        sun.shadows = LightShadows.Soft;
        sun.transform.rotation = Quaternion.Euler(52, -35, 0);

        RenderSettings.skybox = null;
        RenderSettings.sun = sun;
        RenderSettings.ambientMode = AmbientMode.Trilight;
        RenderSettings.ambientSkyColor = new Color(.42f, .47f, .54f);
        RenderSettings.ambientEquatorColor = new Color(.34f, .37f, .41f);
        RenderSettings.ambientGroundColor = new Color(.24f, .26f, .29f);

        var viewer = new GameObject("ShipViewer").AddComponent<ShipViewer>();
        viewer.cam = cam;
        viewer.hullLower = Mat("HullLower", "#9E2F2A", .3f);
        viewer.hullUpper = Mat("HullUpper", "#1B3A66", .4f);
        viewer.deck = Mat("Deck", "#6F8A7A", .2f);
        viewer.house = Mat("House", "#E4E8EE", .3f);
        viewer.accent = Mat("Accent", "#D97F2A", .3f);
        viewer.glass = Mat("Glass", "#202C3C", .8f);
        viewer.steel = Mat("Steel", "#5B6573", .3f);
        viewer.ground = Mat("Ground", "#B4BDC9", .05f);

        EditorSceneManager.SaveScene(scene, ScenePath);
        EditorBuildSettings.scenes = new[] { new EditorBuildSettingsScene(ScenePath, true) };
        AssetDatabase.SaveAssets();
    }

    [System.Serializable]
    class BuildInfo
    {
        public string loaderUrl, dataUrl, frameworkUrl, codeUrl, companyName, productName, productVersion;
    }

    public static void Build()
    {
        Settings();
        Scene();

        string outDir = Path.GetFullPath(OutDir);
        if (Directory.Exists(outDir)) Directory.Delete(outDir, true);
        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
        {
            scenes = new[] { ScenePath },
            locationPathName = outDir,
            target = BuildTarget.WebGL,
            options = BuildOptions.None,
        });
        if (report.summary.result != BuildResult.Succeeded)
        {
            Debug.LogError($"Build failed: {report.summary.result}");
            EditorApplication.Exit(1);
            return;
        }

        File.Delete(Path.Combine(outDir, "index.html"));
        string tpl = Path.Combine(outDir, "TemplateData");
        if (Directory.Exists(tpl)) Directory.Delete(tpl, true);

        string build = Path.Combine(outDir, "Build");
        string Find(string suffix) => Path.GetFileName(Directory.GetFiles(build).Single(f => f.EndsWith(suffix)));
        var info = new BuildInfo
        {
            loaderUrl = Find(".loader.js"),
            dataUrl = Find(".data"),
            frameworkUrl = Find(".framework.js"),
            codeUrl = Find(".wasm"),
            companyName = PlayerSettings.companyName,
            productName = PlayerSettings.productName,
            productVersion = PlayerSettings.bundleVersion,
        };
        File.WriteAllText(Path.Combine(build, "build.json"), JsonUtility.ToJson(info, true));
        Debug.Log($"Build ok: {report.summary.totalSize} bytes -> {build}");
    }
}
