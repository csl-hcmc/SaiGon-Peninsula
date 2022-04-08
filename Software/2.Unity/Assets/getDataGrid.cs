using System.Collections;
using System.Collections.Generic;
using System.Net;
using System.Net.Security;
using System.Security.Cryptography.X509Certificates;
using UnityEngine;
using UnityEngine.Networking;

public class getDataGrid : MonoBehaviour
{
    //public List<GameObject> listgameobject;
    public List<GameObject> list;
    int[] heightData = new int[15];
    private bool check = false;
    void Start()
    {
        getListGameobejct();
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
        UnityWebRequest www = UnityWebRequest.Get("https://csl-hcmc.com/sgp/");
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
            // Debug.Log(lines[5].Split(' ')[33]);
            getAndSetData(lines);
            //for (int i = 0; i < lines.Length-1; i++)
            //{
            //    Debug.Log(lines[i]);
            //    //setHeight(list[i], int.Parse(lines[i].Split(' ')[0]));
            //    //heightData[i] = int.Parse(lines[i][0].ToString());
            //}
           // check = true;
        }
    }
    private void setHeight(GameObject go, int height)
    {
        float yValue = 0.5f + height * 0.3f;
        Vector3 scaleChange = new Vector3(0.3f, yValue, 0.5f);
        go.transform.localScale = scaleChange;
    }
    private void setColor(GameObject go, int value)
    {
        if(value == 3) {
            go.GetComponent<Renderer>().material.color = Color.blue;
        }else if(value == 2)
        {
            go.GetComponent<Renderer>().material.color = Color.green;
        }else if(value == 1)
        {
            go.GetComponent<Renderer>().material.color = Color.red;
        }
        else
        {
            go.GetComponent<Renderer>().material.color = Color.white;
        }
        
    }
    private void getAndSetData(string[] lines)
    {
        setColor(list[9], int.Parse(lines[4].Split(' ')[26]));
        setColor(list[10], int.Parse(lines[4].Split(' ')[27]));
        setColor(list[11], int.Parse(lines[4].Split(' ')[28]));
        setColor(list[12], int.Parse(lines[4].Split(' ')[29]));


        setColor(list[13], int.Parse(lines[5].Split(' ')[33]));
        setColor(list[14], int.Parse(lines[6].Split(' ')[33]));

        setColor(list[5], int.Parse(lines[9].Split(' ')[14]));
        setColor(list[4], int.Parse(lines[10].Split(' ')[12]));
        setColor(list[3], int.Parse(lines[11].Split(' ')[11]));
        setColor(list[2], int.Parse(lines[12].Split(' ')[10]));

        setColor(list[0], int.Parse(lines[12].Split(' ')[4]));
        setColor(list[1], int.Parse(lines[14].Split(' ')[4]));

        setColor(list[6], int.Parse(lines[17].Split(' ')[14]));
        setColor(list[7], int.Parse(lines[19].Split(' ')[16]));
        setColor(list[8], int.Parse(lines[20].Split(' ')[18]));

        check = true;
    }
    private void getListGameobejct()
    {
        
        for(int i = 0; i < this.gameObject.transform.childCount;i++)
        {
            list.Add(this.gameObject.transform.GetChild(i).gameObject);
        }
    }
}
