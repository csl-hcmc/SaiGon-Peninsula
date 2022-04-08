using System.Collections;
using System.Collections.Generic;
using System.Net;
using System.Net.Security;
using System.Security.Cryptography.X509Certificates;
using UnityEngine;
using UnityEngine.Networking;

public class listobject : MonoBehaviour
{
    // Start is called before the first frame update
    public GameObject prefab;
    public List<GameObject> listParentObject;
    public List<Material> listMaterial;
    private bool check = false;
    // Update is called once per frame
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
            for (int i = 0; i < lines.Length - 1; i++)
            {
                change(listParentObject[i], int.Parse(lines[i].Split(' ')[0]));
                //setHeight(list[i], int.Parse(lines[i].Split(' ')[0]));
                //heightData[i] = int.Parse(lines[i][0].ToString());
            }
            check = true;
        }
    }
    private void change(GameObject go, int soTang)
    {
        int child = go.transform.childCount;
        if(child-1 > soTang)
        {
            for(int i = child-1; i > soTang; i--)
            {
                Destroy(go.transform.GetChild(i).gameObject);
            }
        }
        else if(child-1 < soTang)
        {
            int k = Random.Range(0, listMaterial.Count);
            for(int i = child-1; i < soTang; i++)
            {
                Debug.Log("hvt2: " + go.transform.position);
                float yValue = -0.263f + 0.1f * i;
                Debug.Log("yValue: "+yValue);
                 Vector3 positionPrefab = go.transform.position + new Vector3(0f,yValue, 0f);
               // Vector3 positionPrefab = new Vector3(go.transform.position.x, yValue, go.transform.position.z);
                Debug.Log("go.transform.position: " + go.transform.position);
                Debug.Log("positionPrefab: " + positionPrefab);
                //Quaternion rotationPrefab =  Quaternion.Euler(-90f, 0f, 0f);
                GameObject go1=  Instantiate(prefab, go.transform);
                go1.transform.position = positionPrefab;
                go1.GetComponent<Renderer>().material = listMaterial[k];
               // Debug.Log(go1.transform.position);
            }
        }
        float zValue = go.transform.GetChild(soTang).position.z;
        Vector3 abc = new Vector3(0.8549334f, 0.6666667f, zValue);
        go.transform.GetChild(0).localScale = abc;
        //go.transform.GetChild(0).localPosition = new Vector3(3.807f, zValue, 0.581f);
    }
    private void getListGameobejct()
    {

        for (int i = 0; i < this.gameObject.transform.childCount; i++)
        {
            listParentObject.Add(this.gameObject.transform.GetChild(i).gameObject);
        }
    }
}
