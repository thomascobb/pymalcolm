from malcolm.core import BadValueError, method_takes, serialize_object, \
    Update, deserialize_object, Subscribe, MethodModel, Unsubscribe, Queue
from malcolm.modules.builtin.parts import StatefulChildPart
from malcolm.modules.scanning.controllers import RunnableController
from malcolm.modules.scanning.infos import ParameterTweakInfo


ss = RunnableController.stateSet


class RunnableChildPart(StatefulChildPart):
    """Part controlling a child Block that exposes a configure/run interface"""
    # stored between runs
    run_future = None

    # make sure updates are processed in order
    configure_args_update_queue = None

    def update_part_configure_args(self, response, without=()):
        # Decorate validate and configure with the sum of its parts
        if not isinstance(response, Update):
            # Return or Error is the end of our subscription, log and ignore
            self.log.debug(
                "update_part_configure_args got response %r", response)
            return
        configure_model = deserialize_object(response.value, MethodModel)
        # Put data on the queue, so if spawns are handled out of order we
        # still get the most up to date data
        self.configure_args_update_queue.put((configure_model, without))
        self.spawn(self._update_part_configure_args).wait()

    def _update_part_configure_args(self):
        # We spawned just above, so there is definitely something on the
        # queue
        configure_model, without = self.configure_args_update_queue.get(
            timeout=0)
        self.method_models["validate"].recreate_from_others(
            [configure_model], without=without)
        self.method_models["configure"].recreate_from_others(
            [configure_model], without=without)
        self.controller.update_configure_args(
            self, self.method_models["configure"])

    @RunnableController.Init
    def init(self, context):
        self.configure_args_update_queue = Queue()
        super(RunnableChildPart, self).init(context)
        # Monitor the child configure Method for changes
        # TODO: this happens every time writeable changes, is this really good?
        subscription = Subscribe(
            path=[self.params.mri, "configure"],
            callback=self.update_part_configure_args)
        # Wait for the first update to come in
        self.child_controller.handle_request(subscription).wait()

    @RunnableController.Halt
    def halt(self, context):
        super(RunnableChildPart, self).halt(context)
        unsubscribe = Unsubscribe(callback=self.update_part_configure_args)
        self.child_controller.handle_request(unsubscribe)

    @RunnableController.Reset
    def reset(self, context):
        child = context.block_view(self.params.mri)
        if child.abort.writeable:
            child.abort()
        if child.reset.writeable:
            child.reset()

    # MethodMeta will be filled in by update_part_configure_args
    @RunnableController.Validate
    @method_takes()
    def validate(self, context, part_info, params):
        child = context.block_view(self.params.mri)
        returns = child.validate(**params)
        ret = []
        for k, v in returns.items():
            if serialize_object(params[k]) != serialize_object(v):
                ret.append(ParameterTweakInfo(k, v))
        return ret

    # MethodMeta will be filled in by update_part_configure_args
    @RunnableController.Configure
    @method_takes()
    def configure(self, context, completed_steps, steps_to_do, part_info,
                  params):
        child = context.block_view(self.params.mri)
        # If we have done a save or load with the child having a particular
        # design then make sure the child now has that design
        design = self.saved_structure.get("design", "")
        if design:
            child.design.put_value(design)
        child.configure(**params)

    @RunnableController.Run
    def run(self, context, update_completed_steps):
        context.unsubscribe_all()
        child = context.block_view(self.params.mri)
        child.completedSteps.subscribe_value(update_completed_steps, self)
        match_future = self._wait_for_postrun(child)
        self.run_future = child.run_async()
        try:
            context.wait_all_futures(match_future)
        except BadValueError:
            # If child went into Fault state, raise the friendlier run_future
            # exception
            if child.state.value == ss.FAULT:
                raise self.run_future.exception()
            raise

    @RunnableController.PostRunReady
    @RunnableController.PostRunArmed
    def post_run(self, context, completed_steps=None, steps_to_do=None,
                 part_info=None, params=None):
        context.wait_all_futures(self.run_future)

    @RunnableController.Seek
    def seek(self, context, completed_steps, steps_to_do, part_info):
        # Clear out the update_completed_steps and match_future subscriptions
        context.unsubscribe_all()
        child = context.block_view(self.params.mri)
        child.pause(completedSteps=completed_steps)

    @RunnableController.Resume
    def resume(self, context, update_completed_steps):
        child = context.block_view(self.params.mri)
        child.completedSteps.subscribe_value(update_completed_steps, self)
        match_future = self._wait_for_postrun(child)
        child.resume()
        context.wait_all_futures(match_future)

    def _wait_for_postrun(self, child):
        bad_states = [ss.DISABLING, ss.ABORTING, ss.FAULT]
        match_future = child.when_value_matches_async(
            "state", ss.POSTRUN, bad_states)
        return match_future

    @RunnableController.Abort
    def abort(self, context):
        child = context.block_view(self.params.mri)
        child.abort()
