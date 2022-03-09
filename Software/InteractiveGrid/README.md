## Interactive Grid Test Software

### Land Use Ids:

Aurco Ids corresponding the land uses.

L3-SaigonTags.pdf


### GridTest
Processing
Executable:

https://www.dropbox.com/s/qdco7esrz7co0kz/GridTester.zip?dl=0

Test sending grid ids data with UDP, ids correspond the Aruco code, -1 means a non interactive block.


IP: 127.0.0.01

PORT 15810

#### Keys
 - 'n' - create new map with random ids
 - ' ' - send grid data using UDP protocol

Single array of 32 x 50 elements seperated by ' ' and initialize with the string 'in'

Example:

``
in  10 -17 -1 35 -1 9 -1 -1 -1 38 37 35 9 9 9 10 10 10 -1 35 9 9 38 38 38 38 ...
``


### NDI Receiver and Sender Tester

Windows NDI receiver Tester.

Executable:
https://www.dropbox.com/s/cpyyfp2j80n9boj/NDI_WIN%20%281%29.zip?dl=0

#### Keys
 - '1' - create new map with random ids
 - ' ' - send grid data using UDP protocol
