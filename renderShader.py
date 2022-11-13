from PySide6.QtCore import Qt, QThread, QCoreApplication, QObject, Signal, Slot, QRect, QPointF, QRectF, QTimer, QElapsedTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtOpenGL import QOpenGLShader, QOpenGLShaderProgram, QOpenGLWindow, QOpenGLTexture, QOpenGLBuffer
from PySide6.QtGui import QOpenGLFunctions, QOpenGLContext, QImage, QSurfaceFormat, QPainter, QColor, QFont, QBrush, QPen, QLinearGradient
from OpenGL.GL import *
import numpy as np
import dxcam
import mss
import time

screen_capture = "dxcam"
# screen_capture = "mss"


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

        self.frame_time = time.perf_counter()

        self.monitor = Monitor(0, 0, 2560, 1440)
        print(f"x: {self.monitor.x}, y: {self.monitor.y}, w: {self.monitor.w}, h: {self.monitor.h},")
        # return

        if screen_capture == "dxcam":
            self.screenshooter = Screnshooter_dxcam(self.monitor.x, self.monitor.y, self.monitor.w, self.monitor.h)
        else:
            self.screenshooter = Screnshooter_mss(self.monitor.x, self.monitor.y, self.monitor.w, self.monitor.h)
        self.screenshooter.setProperty("Screenshooter", "Screenshoter val")

        self.screenshooter_thread = QThread()
        self.screenshooter_thread.start()
        self.screenshooter.moveToThread(self.screenshooter_thread)

        self.screenshooter.finished.connect(self.refreshTexture, Qt.QueuedConnection)
        
        self.resize(500, 500)



    def initializeGL(self):

        glClearColor(0.2, 0.2, 0.2, 1)
        glEnable(GL_DEPTH_TEST)

        vshader = QOpenGLShader(QOpenGLShader.Vertex, self)
        if not vshader.compileSourceCode(gVShader):
            print(vshader.log())

        fshader = QOpenGLShader(QOpenGLShader.Fragment, self)
        if not fshader.compileSourceCode(gFShader):
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

        # vertex_data = np.array([1, 1, 0,
        #                  1, -1, 0,
        #                 -1, -1, 0,
        #                 -1,  1, 0
        #             ], dtype=np.float32)
        vertex_data = np.array([


                        -1, -1, 0,
                         1, -1, 0,
                         1, 1, 0,
                        -1,  1, 0,
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

        texture_data = np.array([
                        0.0, 1.0,
                        1, 1,
                        1.0, 0.0,
                        0, 0,
                    ], dtype=np.float32)
        self.texture_buffer.allocate(texture_data, texture_data.nbytes)


        self.screen_texture = QOpenGLTexture(QOpenGLTexture.Target2D)
        self.screen_texture.create()
        if screen_capture == "dxcam":
            self.screen_texture.setData(QImage(bytes(bytearray(self.monitor.w * self.monitor.h * 3)),
                    self.monitor.w, self.monitor.h, QImage.Format_RGB888),
                    genMipMaps=QOpenGLTexture.MipMapGeneration.DontGenerateMipMaps)
        else:
            self.screen_texture.setData(QImage(bytes(bytearray(self.monitor.w * self.monitor.h * 4)),
                    self.monitor.w, self.monitor.h, QImage.Format_RGBA8888),
                    genMipMaps=QOpenGLTexture.MipMapGeneration.DontGenerateMipMaps)

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
        # self.timer.start(7)
        QTimer.singleShot(0, self.screenshooter.capture)


    def animationLoop(self):
        # self.update()
        # return
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
        # self.update()
        # return
        self.mss_screen_shot = self.mss_camera.grab(self.monitor)
        if self.mss_screen_shot is not None:
            h = self.mss_screen_shot.height
            w = self.mss_screen_shot.width
            # self.screen_shot =np.ascontiguousarray(self.screen_shot)
            self.screen_texture.setData(0, QOpenGLTexture.PixelFormat.BGRA, QOpenGLTexture.PixelType.UInt8, self.mss_screen_shot.raw)
            # glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE, self.screen_shot)
            self.update()


    def refreshTexture(self, image, cam):
        if cam == "dxcam":
            self.screen_texture.setData(0, QOpenGLTexture.PixelFormat.RGB, QOpenGLTexture.PixelType.UInt8, image)
        elif cam == "mss":
            self.screen_texture.setData(0, QOpenGLTexture.PixelFormat.BGRA, QOpenGLTexture.PixelType.UInt8, image)
        self.update()


    def paintGL(self):
        QTimer.singleShot(0, self.screenshooter.capture)
        old_frame_time = self.frame_time
        self.frame_time = time.perf_counter()
        print(f"Frame: {1/(self.frame_time - old_frame_time)}")

        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self.shader_program.bind()

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

class Screnshooter_mss(QObject):
    started = Signal()
    finished = Signal(bytes, str)

    def __init__(self, x: int, y: int, w: int, h: int):
        super().__init__()
        print(f"x: {x}, y: {y}, w: {w}, h: {h}")
        self.monitor = {"top": x, "left": y, "width": w, "height": h}
        self.camera = mss.mss()


    @Slot()
    def capture(self):
        assert QThread.currentThread() != QCoreApplication.instance().thread()
        screenshot = self.camera.grab(self.monitor)
        self.finished.emit(screenshot.raw, "mss")


class Screnshooter_dxcam(QObject):
    started = Signal()
    finished = Signal(bytes, str)

    def __init__(self, x: int, y: int, w: int, h: int):
        super().__init__()
        self.region = (x, y, w, h)
        self.camera = dxcam.create()


    @Slot()
    def capture(self):
        assert QThread.currentThread() != QCoreApplication.instance().thread()
        
        while True:
            screenshot = self.camera.grab(region=self.region)
            if screenshot is not None:
                break
        self.finished.emit(screenshot.tobytes(), "dxcam")


class Monitor:

    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h


if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    screens = app.screens()
    print(screens)
    screen_geometry = screens[-1].geometry()
    print(screen_geometry)
    # fmt = QSurfaceFormat()
    # fmt.setSamples(4)
    # QSurfaceFormat.setDefaultFormat(fmt)

    # window = MainWindow()
    window = ProjectiveGLViewer()
    window.setScreen(screens[-1])
    window.setPosition(screen_geometry.x(), screen_geometry.y())
    # window.showFullScreen()
    window.show()
    sys.exit(app.exec())
