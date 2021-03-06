from annotypes import add_call_types
from scanpointgenerator import CompoundGenerator

from malcolm.core import Context, Process, Part
from malcolm.modules.pmac.parts import MotorPart
from malcolm.modules.pmac.blocks import raw_motor_block
from malcolm.modules.scanning.controllers import RunnableController
from malcolm.modules.scanning.hooks import ValidateHook, APartInfo
from malcolm.testutil import ChildTestCase


class TestRawMotorPart(ChildTestCase):

    def setUp(self):
        self.process = Process("Process")
        self.context = Context(self.process)
        self.child = self.create_child_block(
            raw_motor_block, self.process, mri="mri", prefix="PV:PRE")
        self.set_attributes(self.child,
                            maxVelocity=5.0,
                            accelerationTime=0.5,
                            readback=12.3,
                            offset=4.5,
                            resolution=0.001,
                            cs="CS1,Y")
        self.o = MotorPart(name="scan", mri="mri")
        self.process.start()

    def tearDown(self):
        del self.context
        self.process.stop(timeout=1)

    def test_report(self):
        returns = self.o.report_status(self.context)
        assert returns.cs_axis == "Y"
        assert returns.cs_port == "CS1"
        assert returns.acceleration == 10.0
        assert returns.resolution == 0.001
        assert returns.offset == 4.5
        assert returns.max_velocity == 5.0
        assert returns.current_position == 12.3
        assert returns.scannable == "scan"

    def test_not_in_cs(self):
        self.set_attributes(self.child, cs="")
        returns = self.o.report_status(self.context)
        assert returns.cs_axis == ""
        assert returns.cs_port == ""
        assert returns.acceleration == 10.0
        assert returns.resolution == 0.001
        assert returns.offset == 4.5
        assert returns.max_velocity == 5.0
        assert returns.current_position == 12.3
        assert returns.scannable == "scan"

    def test_real(self):
        c = RunnableController(mri="top", config_dir="/tmp")
        c.add_part(self.o)

        class ValidatePart(Part):
            data = []

            def setup(self, registrar):
                super(ValidatePart, self).setup(registrar)
                self.register_hooked(ValidateHook, self.validate)

            @add_call_types
            def validate(self, part_info):
                # type: (APartInfo) -> None
                self.data.append(part_info)

        c.add_part(ValidatePart("validate"))
        self.process.add_controller(c)
        c.make_view().validate(CompoundGenerator([], [], []))
        assert len(ValidatePart.data) == 1
        assert list(ValidatePart.data[0]) == ["scan"]
        assert len(ValidatePart.data[0]["scan"]) == 1

