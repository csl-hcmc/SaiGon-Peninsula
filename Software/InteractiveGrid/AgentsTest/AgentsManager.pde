class AgentManager {
  ArrayList<Agent> agents;
  int type;
  color colorType;

  AgentManager() {
    agents = new  ArrayList<Agent>();
  }


  void draw() {
    noStroke();
    fill(colorType);
    for (Agent ag : agents) {
      ag.draw();
    }
  }

  void updateDraw() {
    noStroke();
    fill(colorType);
    for (Agent ag : agents) {
      ag.follow(flowfield);
      ag.run();
    }
  }

  //create agents
  void createAgents(int size, int type) {
    colorType = getAgentTypeColor(type);
    for (int i = 0; i < size; i++) {
      Agent agent = new Agent(new PVector(random(width), random(height)), random(2, 5), random(0.1, 0.5), type);
      agents.add(agent);
    }
  }

  //update Pos
  void updatePos(float posx[], float posy[]) {
    int i =0;
    for (Agent ag : agents) {
      if (i < agents.size()) {
        ag.updatePos(posx[i], posy[i]);
      }
      i++;
    }
  }

  String getStrPos() {
    String pos = "b";
    for ( Agent ag : agents) {
     // pos += " "+String.format("%.1f", ag.position.x)+ " "+String.format("%.1f", ag.position.y);
      pos += " "+String.valueOf((int)ag.position.x)+ " "+ String.valueOf((int)ag.position.y);
    }
    return pos;
  }

  byte[] data = new byte[500*2 +1];
  byte [] getBytePos() {
    data[0] ='a';
    int i =0;
    for ( Agent ag : agents) {
      int idX = i*2;
      int idY = i*2 +1;
      //data[idX] = Char(ag.position.x);
      //data[idY] = char(ag.position.y);
      i++;
    }

    return data;
  }
}
