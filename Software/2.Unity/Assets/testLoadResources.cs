using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

public class testLoadResources : MonoBehaviour
{

    private string[] data;
    public GameObject footPrint;
    private float kcx = 0f;
    private float kcy = 0f;

    // Start is called before the first frame update
    void Start()
    {
        //path text file
        string path = Application.dataPath + "/log.txt";
        //read data in text file
        data = File.ReadAllLines(path);
        //turn on highRise
        highRise();
        //draw heigh highrise
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
    // test
    //load file
    private void loadFile()
    {
        GameObject goFather = this.gameObject.transform.GetChild(0).gameObject.transform.GetChild(1).gameObject;
        for (int i = 0; i < 50; i++)
        {
            GameObject child = Instantiate(Resources.Load("20220314_Building_interact_SGP_Shape_35") as GameObject, goFather.transform);
            //  child.transform.parent = goFather.transform;
        }
    }
    //read text file
    private void readFileTxt()
    {

        for (int i = 0; i < data.Length; i++)
        {

            Debug.Log(data[i].Substring(data[i].LastIndexOf(" ") + 1));
        }
    }
    //draw heigh 
    // load object from resources folder and instantiate
    private void drawHeigh()
    {
        //calculator distance
        Calculator(4, 36);
        // draw footprint
        for (int value = 0; value < 31; value++)
        {
            //set footprint = 4
            int p = 4;
            //get index from text file. index = 100 defaults is 0
            int indexFootPrint = int.Parse(data[value].Substring(data[value].LastIndexOf(" ") + 1));
            if (indexFootPrint != 100)
            {
                //assign father object
                GameObject parentFootPrint = footPrint.gameObject.transform.GetChild(indexFootPrint).gameObject;
                if (parentFootPrint.transform.childCount < 2)
                {
                    for (int n = 0; n < p; n++)
                    {
                        //distance floor
                        float yValue =kcx * n;
                        //set position
                        Vector3 positionPrefab = parentFootPrint.transform.position + new Vector3(0f, yValue, 0f);
                        //Get prefab footprint's name
                        string prefabFootprint = parentFootPrint.transform.GetChild(0).name;
                        //instantiate footprint
                        GameObject child = Instantiate(Resources.Load(prefabFootprint) as GameObject, parentFootPrint.transform);
                        //set position footprint
                        child.transform.position = positionPrefab;
                    }
                }
            }
        }
        for (int i = 0; i < 31; i++)
        {
            // Debug.Log("vao day nua");
            //int k = Random.Range(10, 60);
            //set heigh building
            int k = 36;
            //assign father object
            GameObject parentNew = this.gameObject.transform.GetChild(i).gameObject.transform.GetChild(1).gameObject;
            Debug.Log("name: "+ parentNew.name + " , position: "+ parentNew.transform.position);
            //delete all object/prefab in new parent
            deleteall(parentNew);
            for (int j = 0; j < k; j++)
            {
                //int indexKhoiDe = int.Parse(data[i].Substring(data[i].LastIndexOf(" ") + 1));
                //distance floor
                float yValue = kcy * j;
                //Position prefab
                Vector3 positionPrefab = parentNew.transform.position + new Vector3(0f, yValue, 0f);
                //get name length in text file
                int nameLength = data[i].LastIndexOf(" ") - (data[i].LastIndexOf(")") + 2);
                //get name in text file
                string prefabName = data[i].Substring(data[i].LastIndexOf(")") + 2, nameLength);
                if (prefabName != "newModel542")
                {
                    //instantiate floor
                    GameObject child = Instantiate(Resources.Load(prefabName) as GameObject, parentNew.transform);
                    //set position prefab
                    child.transform.position = positionPrefab;
                }
            }
          //  Debug.Log("Element " + i + ": " + k);
        }
    }

    //draw medium
    private void drawHeighMedium()
    {
        for (int i = 0; i < this.gameObject.transform.childCount; i++)
        {
            //set new father
            GameObject parentNew = this.gameObject.transform.GetChild(i).gameObject.transform.GetChild(2).gameObject;
            //random floor
            int k = Random.Range(10, 60);
            //delete all obejct
            deleteall(parentNew);
            for (int j = 0; j < k; j++)
            {
                float yValue = 0.8f * j;
                Vector3 positionPrefab = parentNew.transform.position + new Vector3(0f, yValue, 0f);
                //instantiate floor
                GameObject child = Instantiate(Resources.Load("Custom/newModel542 100Mid") as GameObject, parentNew.transform);
                child.transform.position = positionPrefab;

            }
        }
    }

    //turn off all object
    private void turnoffall(GameObject go)
    {
        for (int i = 0; i < go.transform.childCount; i++)
        {
            go.transform.GetChild(i).gameObject.SetActive(false);
        }
    }
    //destroy all object
    private void deleteall(GameObject go)
    {
        for (int i = 0; i < go.transform.childCount; i++)
        {
            Destroy(go.transform.GetChild(i).gameObject);
        }
    }
    //turn on lowrise
    private void lowRise()
    {
        for (int i = 0; i < this.gameObject.transform.childCount; i++)
        {
            turnoffall(this.gameObject.transform.GetChild(i).gameObject);
            this.gameObject.transform.GetChild(i).transform.GetChild(3).gameObject.SetActive(true);
        }
    }
    //turn on midrise
    private void midRise()
    {
        for (int i = 0; i < this.gameObject.transform.childCount; i++)
        {
            turnoffall(this.gameObject.transform.GetChild(i).gameObject);
            this.gameObject.transform.GetChild(i).transform.GetChild(2).gameObject.SetActive(true);
        }
    }
    //turn on highrise
    private void highRise()
    {
        for (int i = 0; i < this.gameObject.transform.childCount; i++)
        {
            turnoffall(this.gameObject.transform.GetChild(i).gameObject);
            this.gameObject.transform.GetChild(i).transform.GetChild(1).gameObject.SetActive(true);
        }
    }
    //read text file
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
    //x number footprint
    //y number floor
    private void Calculator(int x, int y)
    {
        kcx = 139 / (x + (7f / 12f) * y);
        kcy = 7f * kcx / 12f;
    }
}
