// import UDP library
import spout.*;
import netP5.*;
import oscP5.*;
import hypermedia.net.*;
import java.util.Arrays;

//viki
OscP5 oscP5;
NetAddress myRemoteLocation;
String remoteIP = "127.0.0.1";
int remotePort = 6969;

UDP udp;  // define the UDP object

PImage gridImg;
float spaceX = 20.370004;
float spaceY = 20.180004;

int [] gridIds = new int[32*50];
int [] gridIdsNoise = new int[32*50];
String[] gridIdsStr = {};

//grid filter
int [] gridIdsFilter = new int[32*50];


float incRec  = 1.68;
float increment = 0.3;

PGraphics mainViewPg;

AgentManager agents;
PGraphics agentsPg;

//Agents

//setup
void setup() {
  size(1920, 1080);

  gridImg = loadImage("grid_map_hd.png");
  //noiseDetail(8, 0.6);

  //generate agent
  agents = new AgentManager();
 // agents.createAgents(500, 1);

  //UDP
  udp = new UDP( this, 15810 );
  udp.listen( true );

  //fill defulta Grid
  fillNoiseGrid();



  //graphics
  agentsPg = createGraphics(1920, 1080);
  mainViewPg  = createGraphics(1920, 1080);
}

//draw
void draw() {
  background(255);

  mainViewPg.beginDraw();
  mainViewPg.noStroke();
  mainViewPg.fill(255, 150);
  mainViewPg.image(gridImg, 0, 0, 1920, 1080);

  for (int i = 0; i < 32; i++) {
    for (int j = 0; j < 50; j++) {
      float recSize = 16;
      float x =  j*spaceX + 758;
      float y =  i*spaceY + 144;

      int index = j + i*50;
      color cId = getColorId(gridIds[index]);

      mainViewPg.fill(cId);
      mainViewPg.noStroke();
      mainViewPg.rect(x, y, recSize, recSize);
      //fill(0);
      //String str = String.valueOf(index);
      //text(str.substring(1, str.length()), x-5, y+10);
      //text(str.substring(0, str.length()), x, y+10);
    }
  }
  mainViewPg.endDraw();

  agentsPg.beginDraw();
  agentsPg.fill(255, 255);
  agentsPg.rect(0, 0, width, height);
  agents.draw(agentsPg);
  agentsPg.endDraw();


  // println(agentPos.length);
  if (agentPos.length > 0) {
    if (agents.getNumAgents() >= 500) {
      for (int i = 0; i < agentPos.length/2 -1; i++) {
        int idX = i*2;
        int idY = i*2 + 1;
        int id = i;
        agents.updatePos(id, Integer.valueOf(agentPos[idX]), Integer.valueOf(agentPos[idY]));
        
        //tmpX[id] = Float.valueOf(agentPos[idX]);
        //tmpY[id] =  Float.valueOf(agentPos[idY]);
      }
    }
  }
 // agents.updatePos(tmpX, tmpY);
  
  

  //image(mainViewPg, 0, 0);
  image(agentsPg, 0, 0);

  fill(0);
  text(frameRate, 50, 50);
}

void keyPressed() {
  if (key == 'n') {
    fillNoiseGrid();
    // gridIds = gridIdsNoise.clone();
  }

  if (key == ' ') {
    println("seding UDP");
    String ip       = "localhost";  // the remote IP address
    int port        = 6100;    // the destination port

    String msg ="in";
    for (int x = 0; x < 32; x++) {
      for (int y = 0; y < 50; y++) {
        int index = y + x*50;
        int id = gridIds[index];
        msg+= " "+id;
      }
    }

    // send the message
    udp.send( msg, ip, port );
    println(msg);
  }

  if (key == 'a') {
    //  spaceX += 0.01;
    //  println("spaceX "+spaceX);
  }
  if (key == 's') {
    //  spaceX -= 0.01;
    //  println("spaceX "+spaceX);
  }

  if (key == 'z') {
    // spaceY += 0.01;
    // println("spaceY "+spaceY);
  }
  if (key == 'x') {
    // spaceY -= 0.01;
    // println("spaceY "+spaceY);
  }
}

//fill with noise values
void fillNoiseGrid() {
  increment = random(0.1, 0.3);
  float xoff = 0.0; // Start xoff at 0
  // For every x,y coordinate in a 2D space, calculate a noise value and produce a brightness value
  for (int x = 0; x <32; x++) {
    xoff += increment;   // Increment xoff
    float yoff = 0.0;   // For every xoff, start yoff at 0
    for (int y = 0; y < 50; y++) {
      yoff += increment; // Increment yoff

      // Calculate noise and scale by 255
      int index = y + x*50;
      float nv = noise(xoff, yoff);
      int tagVal = 17;
      if (nv > 0.0 && nv < 0.35) {
        tagVal = 34;
      }
      if (nv >= 0.35 && nv < 0.5) {
        tagVal = 37;
      }
      if (nv >= 0.4 && nv < 0.6) {
        tagVal = 38;
      }
      gridIdsNoise[index] = tagVal;
      gridIds[index] = tagVal;

      print(tagVal);
      print(" ");
    }
  }
  filterSpaces();
}

//color id
color getColorId(int id) {
  color c = color(0);
  if (id == -1) {
    c = color(255, 0);
  } else if (id  == 17) {//RS
    c = color(#ff00ff);
  } else if (id  == 34) {//RM
    c = color(#b802ff);
  } else if (id  ==13) {//RL
    c = color(#a200ff);
  } else if (id  == 37) {//OS
    c = color(#00ffff);
  } else if (id == 33) {//OM
    c = color(#0099ff);
  } else if (id == 29 ) {//OL
    c = color(#00ffd5);
  } else if (id == 38) { //parks
    c = color(0, 80, 80, 200);
  } else {
    c = color(255, 240, 140, 200);
  }
  return c;
}

//fill empth spaces of the grid
int [] startGrid = {36, 85, 135, 185, 216, 264, 313, 362, 412, 461, 510, 559, 608, 657, 706, 755, 800, 850, 900, 951, 1002, 1053, 1103, 1154, 1204, 1255, 1306, 1357, 1407, 1457, 1521, 1572};
int [] endGrid   = {37, 88, 138, 198, 217, 296, 346, 395, 444, 493, 542, 591, 641, 690, 739, 788, 837, 886, 935, 984, 1033, 1083, 1132, 1181, 1213, 1262, 1311, 1360, 1409, 1458, 1525, 1574};

int [] startGrid2 = {-1, 96, 142, 185, 234, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1215, 1266, 1317, 1366, 1418, 1469, -1, -1};
int [] endGrid2   = {-1, 99, 149, 198, 247, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, 1230, 1278, 1327, 1377, 1426, 1476, -1, -1};

void filterSpaces() {
  for (int x = 0; x <32; x++) {
    for (int y = 0; y < 50; y++) {
      int index = y + x*50;
      if ((index >= startGrid[x] && index <= endGrid[x]) || (index >= startGrid2[x] && index <= endGrid2[x])) {
        continue;
      } else {
        gridIds[index] = -1;
      }
    }
  }
}
