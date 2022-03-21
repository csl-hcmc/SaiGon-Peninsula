String [] agentPos;
float [] tmpX = new float[500];
float [] tmpY = new float[500];

void receive( byte[] data, String ip, int port ) {  // <-- extended handl

  // get the "real" message =
  // forget the ";\n" at the end <-- !!! only for a communication with Pd !!!
  data = subset(data, 0, data.length-1);
  String [] message = new String( data ).split(" ");

  //data = subset(data, 0, data.length-1);
  //String [] message = new String( data ).split(" ");
  if (message.length>0) {
    if (message[0].equals( "b")) {
      agentPos = Arrays.copyOfRange(message, 1, message.length);
    }
  }
}
