/*
class AgentManager {
  ArrayList<Agent> agents;
  int type;
  color colorType;

  AgentManager() {
    agents = new  ArrayList<Agent>();
  }
  
  int getNumAgents(){
    return agents.size();
  }


  void draw(PGraphics pg) {
    pg.noStroke();
    pg.fill(colorType);
    for (Agent ag : agents) {
      ag.draw(pg);
    }
  }

  //create agents
  void createAgents(int size, int type) {
    colorType = getAgentTypeColor(type);
    for (int i = 0; i < size; i++) {
      Agent agent = new Agent(type);
      agents.add(agent);
    }
  }

  //update Pos
  void updatePos(int id, float posx, float posy) {
    (agents.get(id)).x = posx;
    (agents.get(id)).y = posy;
  }

  void updatePos(float posx[], float posy[]) {
    int i =0;
    for (Agent ag : agents) {
      if (i < agents.size()) {
        ag.updatePos(posx[i], posy[i]);
      }
      i++;
    }
  }
}



  // println(agentPos.length);
  if (agentPos.length > 0) {
    if (agents.getNumAgents() >= 500) {
      for (int i = 0; i < agentPos.length/2 -1; i++) {
        int idX = i*2;
        int idY = i*2 + 1;
        tmpX[id] = Float.valueOf(agentPos[idX ]);
         tmpY[id]=  Float.valueOf(agentPos[idY]);
      
        agents.updatePos(id, posx, posy);
      }
    }
  }
*/
