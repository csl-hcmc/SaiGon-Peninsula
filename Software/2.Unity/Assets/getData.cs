using System.Collections;
using System.Collections.Generic;
using System.Net;
using System.Net.Security;
using System.Security.Cryptography.X509Certificates;
using UnityEngine;
using UnityEngine.Networking;

public class getData : MonoBehaviour
{
    public List<GameObject> list;
    int[] heightData = new int[15];
    private bool check = false;
    void Start()
    {
        ServicePointManager.ServerCertificateValidationCallback = TrustCertificate;
        StartCoroutine(GetText());
    }
    private void Update()
    {
        if (check)
        {
            check = false;
            StartCoroutine(GetText());
        }
    }
    private static bool TrustCertificate(object sender, X509Certificate x509Certificate, X509Chain x509Chain, SslPolicyErrors sslPolicyErrors)
    {
        // all Certificates are accepted
        return true;
    }
    IEnumerator GetText()
    {
        UnityWebRequest www = UnityWebRequest.Get("http://csl-hcmc.com:7777/");
        yield return www.SendWebRequest();

        if (www.result != UnityWebRequest.Result.Success)
        {
            Debug.Log(www.error);
        }
        else
        {
            // Show results as text
            Debug.Log(www.downloadHandler.text);
            string tmp = www.downloadHandler.text;
            var lines = tmp.Split('\n');
            for (int i = 0; i < lines.Length-1; i++)
            {
                setHeight(list[i], int.Parse(lines[i].Split(' ')[0]));
                //heightData[i] = int.Parse(lines[i][0].ToString());
            }
            check = true;
        }
    }
    private void setHeight(GameObject go, int height)
    {
        float yValue = 0.5f + height * 0.3f;
        Vector3 scaleChange = new Vector3(0.3f, yValue, 0.5f);
        go.transform.localScale = scaleChange;
    }
}
