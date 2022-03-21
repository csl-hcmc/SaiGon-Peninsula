class AgentManager {
  int type;
  color colorType;

  int numAgents = 500;

  float [] posX = new float[numAgents];
  float [] posY = new float[numAgents];

  AgentManager() {
  }

  int getNumAgents() {
    return numAgents;
  }


  void draw(PGraphics pg) {
    pg.noStroke();
    pg.fill(colorType);

    for (int i = 0; i < 500; i++) {
      pg.ellipse(posX[i], posY[i], 20, 20);
    }
  }

  void updatePos(int id, float posx, float posy) {
    posX[id] = posx;
    posY[id] = posy;
  }

  void updatePos(float posx[], float posy[]) {
    posX = Arrays.copyOf(posx, posx.length);
    posY = Arrays.copyOf(posy, posy.length);
  }
}
