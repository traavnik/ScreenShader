from PySide6.QtCore import Qt, QRect, QPointF, QRectF, QTimer, QElapsedTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtOpenGL import QOpenGLShader, QOpenGLShaderProgram, QOpenGLWindow, QOpenGLTexture, QOpenGLBuffer
from PySide6.QtGui import QOpenGLFunctions, QOpenGLContext, QImage, QSurfaceFormat, QPainter, QColor, QFont, QBrush, QPen, QLinearGradient
from OpenGL.GL import *
import numpy as np
import dxcam
import mss

# screen_capture = "dxcam"
screen_capture = "mss"

class MainWindow(QMainWindow):


    def __init__(self):
        super().__init__()

        # camera = dxcam.create()

        # left, top = 0, 0
        # right, bottom = left + 640, top + 640
        # region = (left, top, right, bottom)
        # screen_shot = camera.grab(region=region)

        helper = Helper()
        # openGL = GLWidget(helper, self)
        openGL2 = ProjectiveGLViewer(self)
        layout = QGridLayout()
        # layout.addWidget(openGL, 0, 0)
        layout.addWidget(openGL2, 0, 0)
        self.setLayout(layout)

        # timer = QTimer(self)
        # timer.timeout.connect(openGL.animate)
        # timer.start(10)


class Helper(object):
    def __init__(self):
        gradient = QLinearGradient(QPointF(50, -20), QPointF(80, 20))
        gradient.setColorAt(0.0, Qt.white)
        gradient.setColorAt(1.0, QColor(0xa6, 0xce, 0x39))

        self.background = QBrush(QColor(64, 32, 64))
        self.circleBrush = QBrush(gradient)
        self.circlePen = QPen(Qt.black)
        self.circlePen.setWidth(1)
        self.textPen = QPen(Qt.white)
        self.textFont = QFont()
        self.textFont.setPixelSize(50)

    def paint(self, painter, event, elapsed):
        painter.fillRect(event.rect(), self.background)
        painter.translate(100, 100)

        painter.save()
        painter.setBrush(self.circleBrush)
        painter.setPen(self.circlePen)
        painter.rotate(elapsed * 0.030)

        r = elapsed / 1000.0
        n = 30
        for i in range(n):
            painter.rotate(30)
            radius = 0 + 120.0*((i+r)/n)
            circleRadius = 1 + ((i+r)/n)*20
            painter.drawEllipse(QRectF(radius, -circleRadius,
                    circleRadius*2, circleRadius*2))

        painter.restore()

        painter.setPen(self.textPen)
        painter.setFont(self.textFont)
        painter.drawText(QRect(-50, -50, 100, 100), Qt.AlignmentFlag.AlignCenter, "Qt")


class GLWidget(QOpenGLWidget):
    def __init__(self, helper, parent):
        super(GLWidget, self).__init__(parent)

        self.helper = helper
        self.elapsed = 0
        self.setFixedSize(200, 200)
        self.setAutoFillBackground(False)

    def animate(self):
        self.elapsed = (self.elapsed + self.sender().interval()) % 1000
        self.update()

    def paintEvent(self, event):
        painter = QPainter()
        painter.begin(self)
        painter.setRenderHint(QPainter.Antialiasing)
        self.helper.paint(painter, event, self.elapsed)
        painter.end()


gVShader = """
            #version 330 core
            layout (location = 0) in vec3 aPos;
            layout (location = 1) in vec2 aTexCoord;

            out vec2 vTexCoord;

            void main()
            {
                gl_Position = vec4(aPos, 1.0);
                vTexCoord = aTexCoord;
            }"""

gFShader = """
            #version 330 core
            out vec4 FragColor;

            in vec2 vTexCoord;

            uniform sampler2D ourTexture;

            void main()
            {
                FragColor = texture(ourTexture, vTexCoord);
                //FragColor = vec4(1.0, 0.0, 0.0, 0.5);
            }"""

gFShaderSwirl = """
            #version 330 core
            #define PI 3.14159
            out vec4 FragColor;

            in vec2 vTexCoord;

            uniform sampler2D ourTexture;

            void main()
            {
                float effectRadius = .5;
                float effectAngle = 0.5 * PI;

                vec2 uv = vTexCoord.xy / 1. - vec2(.5, .5);

                float len = length(uv * vec2(1., 1.));
                float angle = atan(uv.y, uv.x) + effectAngle * smoothstep(effectRadius, 0., len);
                float radius = length(uv);

                FragColor = texture(ourTexture, vec2(radius * cos(angle), radius * sin(angle)) + 0.5);
            }"""
class ProjectiveGLViewer(QOpenGLWindow):

    image_id_pub = None

    def __init__(self):
        super().__init__()

        if screen_capture == "dxcam":
            self.camera = dxcam.create()

            left, top = 880, 320
            right, bottom = left + 800, top + 800
            self.region = (left, top, right, bottom)
            self.screen_shot = self.camera.grab(region=self.region)
            # self.screen_shot = self.camera.grab()
        else:
            self.monitor = {"top": 0, "left": 0, "width": 1920, "height": 1080}
            self.mss_camera = mss.mss()
            self.mss_screen_shot = self.mss_camera.grab(self.monitor)
        self.resize(500, 500)



    def initializeGL(self):

        glClearColor(0.2, 0.2, 0.2, 1)
        glEnable(GL_DEPTH_TEST)

        vshader = QOpenGLShader(QOpenGLShader.Vertex, self)
        if not vshader.compileSourceCode(gVShader):
            print(vshader.log())

        fshader = QOpenGLShader(QOpenGLShader.Fragment, self)
        if not fshader.compileSourceCode(gFShaderSwirl):
            print(fshader.log())

        self.shader_program = QOpenGLShaderProgram()
        self.shader_program.addShader(vshader)
        self.shader_program.addShader(fshader)
        self.shader_program.link()
        self.shader_program.bind()

        self.shader_program.bindAttributeLocation("aPos", 0)
        self.shader_program.bindAttributeLocation("aTexCoord", 1)
        self.shader_program.bind()

        self.vert_buffer = QOpenGLBuffer()
        self.vert_buffer.create()
        self.vert_buffer.bind()

        vertex_data = np.array([1, 1, 0,
                         1, -1, 0,
                        -1, -1, 0,
                        -1,  1, 0
                    ], dtype=np.float32)
        self.vert_buffer.allocate(vertex_data, vertex_data.nbytes)

        self.indices_buffer = QOpenGLBuffer(QOpenGLBuffer.IndexBuffer)
        self.indices_buffer.create()
        self.indices_buffer.bind()

        indice_data = np.array([
                        0, 1, 3,
                        1, 2, 3
                    ], dtype=np.uint32)
        self.indices_buffer.allocate(indice_data, indice_data.nbytes)


        self.texture_buffer = QOpenGLBuffer()
        self.texture_buffer.create()
        self.texture_buffer.bind()

        texture_data = np.array([1, 1,
                        1.0, 0.0,
                        0, 0,
                        0.0, 1.0
                    ], dtype=np.float32)
        self.texture_buffer.allocate(texture_data, texture_data.nbytes)


        self.screen_texture = QOpenGLTexture(QOpenGLTexture.Target2D)
        self.screen_texture.create()
        if screen_capture == "dxcam":
            h, w, _ = self.screen_shot.shape
            self.screen_shot =np.ascontiguousarray(self.screen_shot)
            print(f'Image width: {w}, height: {h}')
            print(self.screen_shot.flags)
            # self.screen_texture.setData(QImage(self.screen_shot.data, w, h, 3 * w, QImage.Format_RGB888))
            self.screen_texture.setData(QImage(self.screen_shot.data, w, h, 3 * w, QImage.Format_RGB888), genMipMaps=QOpenGLTexture.MipMapGeneration.DontGenerateMipMaps)
        else:
            h = self.mss_screen_shot.height
            w = self.mss_screen_shot.width
            print(f'Image width: {w}, height: {h}')
            self.screen_texture.setData(QImage(self.mss_screen_shot.raw, w, h, QImage.Format_RGBA8888), genMipMaps=QOpenGLTexture.MipMapGeneration.DontGenerateMipMaps)
        self.screen_texture.setMinMagFilters(QOpenGLTexture.Linear, QOpenGLTexture.Linear)
        self.screen_texture.setWrapMode(QOpenGLTexture.ClampToEdge)

        self.timer = QTimer()
        if screen_capture == "dxcam":
            self.timer.timeout.connect(self.animationLoop)
        else:
            self.timer.timeout.connect(self.animationLoop_mss)
        # self.elapsed_timer = QElapsedTimer()
        # self.elapsed_timer.start()
        # self.delta_time = 0
        self.timer.start(7)


    def animationLoop(self):
        self.update()
        return
        # Need to avoid timer usage and do native dxcam update
        # self.screen_shot = self.camera.grab(region=self.region)
        self.screen_shot = self.camera.grab()

        if self.screen_shot is not None:
            h, w, _ = self.screen_shot.shape
            # self.screen_shot =np.ascontiguousarray(self.screen_shot)
            # Faster ways to update: https://stackoverflow.com/questions/3887636/how-to-manipulate-texture-content-on-the-fly/10702468#10702468
            self.screen_texture.setData(0, QOpenGLTexture.PixelFormat.RGB, QOpenGLTexture.PixelType.UInt8, self.screen_shot)
            # glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE, self.screen_shot)
            self.update()

    def animationLoop_mss(self):
        self.update()
        return
        self.mss_screen_shot = self.mss_camera.grab(self.monitor)
        if self.mss_screen_shot is not None:
            h = self.mss_screen_shot.height
            w = self.mss_screen_shot.width
            # self.screen_shot =np.ascontiguousarray(self.screen_shot)
            # Faster ways to update: https://stackoverflow.com/questions/3887636/how-to-manipulate-texture-content-on-the-fly/10702468#10702468
            self.screen_texture.setData(0, QOpenGLTexture.PixelFormat.BGRA, QOpenGLTexture.PixelType.UInt8, self.mss_screen_shot.raw)
            # glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE, self.screen_shot)
            self.update()



    def paintGL(self):
        if screen_capture == "dxcam":
            self.screen_shot = self.camera.grab(region=self.region)
            if self.screen_shot is not None:
                self.screen_texture.setData(0, QOpenGLTexture.PixelFormat.RGB, QOpenGLTexture.PixelType.UInt8, np.ascontiguousarray(self.screen_shot))
        else:
            self.mss_screen_shot = self.mss_camera.grab(self.monitor)
            self.screen_texture.setData(0, QOpenGLTexture.PixelFormat.BGRA, QOpenGLTexture.PixelType.UInt8, self.mss_screen_shot.raw)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        # self.shader_program.bind()

        self.vert_buffer.bind()
        self.shader_program.setAttributeBuffer(0, GL_FLOAT, 0, 3)
        self.shader_program.enableAttributeArray(0)

        # self.indices_buffer.bind()

        self.texture_buffer.bind()
        self.shader_program.setAttributeBuffer(1, GL_FLOAT, 0, 2)
        self.shader_program.enableAttributeArray(1)

        # self.shader_program.bind()
        self.screen_texture.bind()
        # glDrawArrays(GL_TRIANGLES, 0, 6)
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, None)



    # def resizeGL(self, w, h):
    #     glViewport(0, 0, w, h)
    #     return


if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    screens = app.screens()
    screen_geometry = screens[-1].geometry()
    print(screen_geometry)
    # fmt = QSurfaceFormat()
    # fmt.setSamples(4)
    # QSurfaceFormat.setDefaultFormat(fmt)

    # window = MainWindow()
    window = ProjectiveGLViewer()
    window.setScreen(screens[-1])
    window.showFullScreen()
    # window.setWindowFlags(Qt.CustomizeWindowHint  | Qt.FramelessWindowHint)
    # window.show()
    sys.exit(app.exec())
