// import UDP library
import spout.*;
import netP5.*;
import oscP5.*;
import hypermedia.net.*;
import java.util.Arrays;

UDP udp;  // define the UDP object

float incRec  = 1.68;
float increment = 0.3;


FlowField flowfield;
AgentManager agents;

void setup() {
  size(1920, 1080);
  frameRate(30);

  flowfield = new FlowField(20);

  agents = new AgentManager();
  agents.createAgents(250, 1);

  //UDP
  udp = new UDP( this, 15809 );
  udp.listen( true );
}

void draw() {
  background(255);
  flowfield.display();
  
  agents.updateDraw();
  //udp
  agentsSendPos();

  fill(0);
  text(frameRate, 20, 20);
}

// Make a new flowfield
void mousePressed() {
  flowfield.init();
}


//Agent types
color getAgentTypeColor(int type) {
  color c = color(0);
  if (type == 0) { //default type
    c = color(0, 100, 100);
  }
  if (type ==1) { //bikes
    c = color(0, 200, 150);
  }
  if (type ==2) { //people
    c = color(100, 0, 150);
  }
  if (type ==3) { //cars
    c = color(100, 100, 0);
  }
  if (type ==4) { //motorbikes
    c = color(100, 120, 150);
  }
  return  c;
}
