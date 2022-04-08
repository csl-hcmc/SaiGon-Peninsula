using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

public class testLoadResources : MonoBehaviour
{

    private string[] data;
    public GameObject KhoiDe;
    private float kcx = 0f;
    private float kcy = 0f;

    // Start is called before the first frame update
    void Start()
    {
        string path = Application.dataPath + "/log.txt";
        data = File.ReadAllLines(path);
        highRise();
        drawHeigh();
    }

    // Update is called once per frame
    void Update()
    {
        if (Input.GetKey(KeyCode.L))
        {
            // loadFile();
            lowRise();
        }
        if (Input.GetKey(KeyCode.K))
        {
            readFileTxt();
        }
        if (Input.GetKey(KeyCode.D))
        {
            drawHeigh();
        }
        if (Input.GetKey(KeyCode.M))
        {
            midRise();
        }
        if (Input.GetKey(KeyCode.H))
        {
            highRise();
        }
        if (Input.GetKey(KeyCode.P))
        {
            drawHeighMedium();
        }
        if (Input.GetKey(KeyCode.Space))
        {
            readAllFileTxt();
        }
    }
    private void loadFile()
    {
        GameObject goFather = this.gameObject.transform.GetChild(0).gameObject.transform.GetChild(1).gameObject;
        for (int i = 0; i < 50; i++)
        {
            GameObject child = Instantiate(Resources.Load("20220314_Building_interact_SGP_Shape_35") as GameObject, goFather.transform);
            //  child.transform.parent = goFather.transform;
        }
    }
    private void readFileTxt()
    {

        for (int i = 0; i < data.Length; i++)
        {

            Debug.Log(data[i].Substring(data[i].LastIndexOf(" ") + 1));
        }
    }
    private void drawHeigh()
    {
        Calculator(4, 36);
        for (int value = 0; value < 31; value++)
        {
            int p = 4;
            int indexKhoiDe = int.Parse(data[value].Substring(data[value].LastIndexOf(" ") + 1));
            if (indexKhoiDe != 100)
            {
                GameObject parentKhoiDe = KhoiDe.gameObject.transform.GetChild(indexKhoiDe).gameObject;
                if (parentKhoiDe.transform.childCount < 2)
                {
                    for (int n = 0; n < p; n++)
                    {
                        float yValue =kcx * n;
                        Vector3 positionPrefab = parentKhoiDe.transform.position + new Vector3(0f, yValue, 0f);
                        string prefabDe = parentKhoiDe.transform.GetChild(0).name;
                        GameObject child = Instantiate(Resources.Load(prefabDe) as GameObject, parentKhoiDe.transform);
                        child.transform.position = positionPrefab;
                    }
                }
            }
        }
        for (int i = 0; i < 31; i++)
        {
            // Debug.Log("vao day nua");
            //int k = Random.Range(10, 60);
            int k = 36;
            GameObject parentNew = this.gameObject.transform.GetChild(i).gameObject.transform.GetChild(1).gameObject;
            Debug.Log("name: "+ parentNew.name + " , position: "+ parentNew.transform.position);
            deleteall(parentNew);
            for (int j = 0; j < k; j++)
            {
                int indexKhoiDe = int.Parse(data[i].Substring(data[i].LastIndexOf(" ") + 1));
                float yValue = kcy * j;

                Vector3 positionPrefab = parentNew.transform.position + new Vector3(0f, yValue, 0f);
                int dodai = data[i].LastIndexOf(" ") - (data[i].LastIndexOf(")") + 2);
                string prefabName = data[i].Substring(data[i].LastIndexOf(")") + 2, dodai);
                if (prefabName != "newModel542")
                {
                    GameObject child = Instantiate(Resources.Load(prefabName) as GameObject, parentNew.transform);
                    child.transform.position = positionPrefab;
                }
            }
          //  Debug.Log("Element " + i + ": " + k);
        }
    }

    private void drawHeighMedium()
    {
        for (int i = 0; i < this.gameObject.transform.childCount; i++)
        {
            GameObject parentNew = this.gameObject.transform.GetChild(i).gameObject.transform.GetChild(2).gameObject;
            int k = Random.Range(10, 60);
            deleteall(parentNew);
            for (int j = 0; j < k; j++)
            {
                float yValue = 0.8f * j;
                Vector3 positionPrefab = parentNew.transform.position + new Vector3(0f, yValue, 0f);
                GameObject child = Instantiate(Resources.Load("Custom/newModel542 100Mid") as GameObject, parentNew.transform);
                child.transform.position = positionPrefab;

            }
        }
    }

    private void turnoffall(GameObject go)
    {
        for (int i = 0; i < go.transform.childCount; i++)
        {
            go.transform.GetChild(i).gameObject.SetActive(false);
        }
    }
    private void deleteall(GameObject go)
    {
        for (int i = 0; i < go.transform.childCount; i++)
        {
            Destroy(go.transform.GetChild(i).gameObject);
        }
    }
    private void lowRise()
    {
        for (int i = 0; i < this.gameObject.transform.childCount; i++)
        {
            turnoffall(this.gameObject.transform.GetChild(i).gameObject);
            this.gameObject.transform.GetChild(i).transform.GetChild(3).gameObject.SetActive(true);
        }
    }
    private void midRise()
    {
        for (int i = 0; i < this.gameObject.transform.childCount; i++)
        {
            turnoffall(this.gameObject.transform.GetChild(i).gameObject);
            this.gameObject.transform.GetChild(i).transform.GetChild(2).gameObject.SetActive(true);
        }
    }
    private void highRise()
    {
        for (int i = 0; i < this.gameObject.transform.childCount; i++)
        {
            turnoffall(this.gameObject.transform.GetChild(i).gameObject);
            this.gameObject.transform.GetChild(i).transform.GetChild(1).gameObject.SetActive(true);
        }
    }
    private void readAllFileTxt()
    {

        for (int i = 0; i < data.Length; i++)
        {
            //Debug.Log(data[i].LastIndexOf(" "));
            Debug.Log(data[i].Substring(data[i].LastIndexOf(" ") +1));
           // Debug.Log(data[i].LastIndexOf(" "));
           // Debug.Log(data[i].LastIndexOf(')'));
            //int dodai = data[i].LastIndexOf(" ") - (data[i].LastIndexOf(")") + 2);
           //Debug.Log( data[i].Substring(data[i].LastIndexOf(")")+2, dodai));
           
            //Debug.Log(data[i].Substring(data[i].LastIndexOf(" ") + 1));
        }
    }
    //x so tang de
    //y so tang toa nha
    private void Calculator(int x, int y)
    {
        kcx = 139 / (x + (7f / 12f) * y);
        kcy = 7f * kcx / 12f;
    }
}
