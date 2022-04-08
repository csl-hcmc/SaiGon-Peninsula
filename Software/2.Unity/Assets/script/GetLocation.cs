using System.Collections;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

public class GetLocation : MonoBehaviour
{
    public List<GameObject> listGameobject;
    string content;
    // Start is called before the first frame update
    void Start()
    {
        getListGameobejct();
       // string path = Application.dataPath+"/log.txt";
       // Debug.Log(path);
       // for(int i=0; i < listGameobject.Count; i++)
        //{
            //Debug.Log("position: "+listGameobject[i].transform.position);
            //Debug.Log("rotation: "+listGameobject[i].transform.rotation);
            //Debug.Log(listGameobject[i].transform.GetChild(1).transform.GetChild(2).name);
        //    content = content+ listGameobject[i].transform.position+" "+  listGameobject[i].transform.rotation + " " + listGameobject[i].transform.GetChild(1).transform.GetChild(1).name + "\n";
        //}
       // Debug.Log(content);
       // File.WriteAllText(path, content);
    }

    // Update is called once per frame
    void Update()
    {
       
    }
    private void getListGameobejct()
    {

        for (int i = 0; i < this.gameObject.transform.childCount; i++)
        {
            listGameobject.Add(this.gameObject.transform.GetChild(i).gameObject);
        }
    }
}
