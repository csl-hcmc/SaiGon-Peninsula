using System.Collections;
using System.Collections.Generic;
using System.Net;
using System.Net.Security;
using System.Security.Cryptography.X509Certificates;
using UnityEngine;
using UnityEngine.Networking;

public class getDataGridModel : MonoBehaviour
{
    //public List<GameObject> listgameobject;
    public GameObject prefab;
    public GameObject prefabMid;
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
    private void setObjectActive(GameObject go, int value, int soTang)
    {
        if(value == 3) {
            changeObject(go, 1, soTang);
            //go.GetComponent<Renderer>().material.color = Color.blue;
        }else if(value == 2)
        {
            changeObject(go, 2, soTang);
            //go.GetComponent<Renderer>().material.color = Color.green;
        }
        else if(value == 1)
        {
            changeObject(go, 3, soTang);
            // go.GetComponent<Renderer>().material.color = Color.red;
        }
        else
        {
            changeObject(go, 0, soTang);
            //go.GetComponent<Renderer>().material.color = Color.white;
        }
        
    }
    private void getAndSetData(string[] lines)
    {
        setObjectActive(list[9], int.Parse(lines[4].Split(' ')[26].Substring(0,2)), int.Parse(lines[4].Split(' ')[26].Substring(2, 2)));
        setObjectActive(list[10], int.Parse(lines[4].Split(' ')[27].Substring(0, 2)), int.Parse(lines[4].Split(' ')[27].Substring(2, 2)));
        setObjectActive(list[11], int.Parse(lines[4].Split(' ')[28].Substring(0, 2)), int.Parse(lines[4].Split(' ')[28].Substring(2, 2)));
        setObjectActive(list[12], int.Parse(lines[4].Split(' ')[29].Substring(0, 2)), int.Parse(lines[4].Split(' ')[29].Substring(2, 2)));

        setObjectActive(list[13], int.Parse(lines[5].Split(' ')[33].Substring(0, 2)), int.Parse(lines[5].Split(' ')[33].Substring(2, 2)));
        setObjectActive(list[14], int.Parse(lines[6].Split(' ')[33].Substring(0, 2)), int.Parse(lines[6].Split(' ')[33].Substring(2, 2)));

        setObjectActive(list[5], int.Parse(lines[9].Split(' ')[14].Substring(0, 2)), int.Parse(lines[9].Split(' ')[14].Substring(2, 2)));
        setObjectActive(list[4], int.Parse(lines[10].Split(' ')[12].Substring(0, 2)), int.Parse(lines[10].Split(' ')[12].Substring(2, 2)));
        setObjectActive(list[3], int.Parse(lines[11].Split(' ')[11].Substring(0, 2)), int.Parse(lines[11].Split(' ')[11].Substring(2, 2)));
        setObjectActive(list[2], int.Parse(lines[12].Split(' ')[10].Substring(0, 2)), int.Parse(lines[12].Split(' ')[10].Substring(2, 2)));

        setObjectActive(list[0], int.Parse(lines[12].Split(' ')[4].Substring(0, 2)), int.Parse(lines[12].Split(' ')[4].Substring(2, 2)));
        setObjectActive(list[1], int.Parse(lines[14].Split(' ')[4].Substring(0, 2)), int.Parse(lines[14].Split(' ')[4].Substring(2, 2)));

        setObjectActive(list[6], int.Parse(lines[17].Split(' ')[14].Substring(0, 2)), int.Parse(lines[17].Split(' ')[14].Substring(2, 2)));
        setObjectActive(list[7], int.Parse(lines[19].Split(' ')[16].Substring(0, 2)), int.Parse(lines[19].Split(' ')[16].Substring(2, 2)));
        setObjectActive(list[8], int.Parse(lines[20].Split(' ')[18].Substring(0, 2)), int.Parse(lines[20].Split(' ')[18].Substring(2, 2)));

        check = true;
    }
    private void changeObject(GameObject go, int k, int soTang)
    {
        for (int i = 0; i < go.transform.childCount; i++)
        {
            go.transform.GetChild(i).gameObject.SetActive(false);
        }
        go.transform.GetChild(k).gameObject.SetActive(true);
        if (k == 1)
        {
            GameObject newFather = go.transform.GetChild(1).gameObject;
            change(newFather, soTang, prefab);
        }else if (k == 2)
        {
            GameObject newFather = go.transform.GetChild(2).gameObject;
            change(newFather, soTang, prefabMid);
        }
    }
    private void getListGameobejct()
    {
        
        for(int i = 0; i < this.gameObject.transform.childCount;i++)
        {
            list.Add(this.gameObject.transform.GetChild(i).gameObject);
        }
    }
    private void change(GameObject go, int soTang, GameObject prefabModel)
    {
        int child = go.transform.childCount;
        if (child - 1 > soTang)
        {
            for (int i = child - 1; i > soTang; i--)
            {
                Destroy(go.transform.GetChild(i).gameObject);
            }
        }
        else if (child - 1 < soTang)
        {
           // int k = Random.Range(0, listMaterial.Count);
            for (int i = child - 1; i < soTang; i++)
            {
                Debug.Log("hvt2: " + go.transform.position);
                float yValue =  0.8f * i;
                Debug.Log("yValue: " + yValue);
                Vector3 positionPrefab = go.transform.position + new Vector3(0f, yValue, 0f);
                Debug.Log("go.transform.position: " + go.transform.position);
                Debug.Log("positionPrefab: " + positionPrefab);
                GameObject go1 = Instantiate(prefabModel, go.transform);
                go1.transform.position = positionPrefab;
            }
        }
        //float zValue = go.transform.GetChild(soTang).position.z;
        float zValue =0f;
        if (soTang < 50) {
            zValue = 0.013f * (soTang + soTang * 0.1f);
        }else
            zValue = 0.013f * (soTang + soTang * 0.2f);

        float xValueNgoai = go.transform.GetChild(0).localScale.x;
        float yValueNgoai = go.transform.GetChild(0).localScale.y;
        Vector3 abc = new Vector3(xValueNgoai, yValueNgoai, zValue);
        go.transform.GetChild(0).localScale = abc;
        //go.transform.GetChild(0).localPosition = new Vector3(3.807f, zValue, 0.581f);
    }
}
