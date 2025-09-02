// udpcommodule.c
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <time.h>
#include <string.h>
#include <stdint.h>
#include <bits/time.h>
#include <stdlib.h>
#include <sched.h>
#include <stdbool.h>
#include <stdatomic.h>
#include <stdio.h>
#include <pthread.h>
#include <fcntl.h>
#include <poll.h>

#define MAX(a, b) ((a) > (b) ? (a) : (b))
#define MIN(a, b) ((a) > (b) ? (b) : (a))

#define MAX_UDP_PAYLOAD 1500


char buff[100];


static inline long long now_ns(clockid_t clock) {
	struct timespec ts;
	clock_gettime(clock, &ts);
	return ts.tv_sec * 1000000000LL + ts.tv_nsec;
}


static inline struct timespec ts_from_ns(long long time_ns){
	struct timespec ts = {
			.tv_sec = time_ns / 1000000000ULL,
			.tv_nsec = time_ns % 1000000000ULL
	};
	return ts;
}

static inline struct timespec future_ts(long long time_ns, clockid_t clock){
	long long future_ns = now_ns(clock) + time_ns;
	return ts_from_ns(future_ns);
}


typedef struct packet {
	long long ts;
	char data[MAX_UDP_PAYLOAD];
	size_t len;
} Packet_t;

typedef enum {
	DIR_SEND, // half duplex send
	DIR_RECV, // half duplex recieve
	DIR_FULL, // full duplex
}DIRECTION_t;

typedef struct PacketStats{
 uint32_t n_packets_req;
 uint32_t n_packets_sent;
 uint32_t n_packets_rec;
 uint32_t n_rx_packets_dropped;
 uint32_t n_tx_packets_dropped;
 long long max_latency_ns;
 long long min_latency_ns;
 uint64_t total_latency_ns;
 uint32_t histo_start;
 uint32_t histo_div;
 uint32_t histogram[128];
 uint32_t n_send_ticks;
 uint32_t n_rec_ticks;
 uint32_t n_imediate_packets;
} PacketStats_t;

typedef struct {
	unsigned capacity;
	atomic_size_t head;
	atomic_size_t tail;
	pthread_cond_t cond_not_full;
	pthread_cond_t cond_not_empty;
	pthread_mutex_t cond_mutex;
	Packet_t* data;
} Ringbuffer;



int buff_init(Ringbuffer* buff, size_t capacity){
	pthread_cond_t cond_not_full = PTHREAD_COND_INITIALIZER;
	pthread_cond_t cond_not_empty = PTHREAD_COND_INITIALIZER;
	pthread_mutex_t cond_mutex = PTHREAD_MUTEX_INITIALIZER;

	buff->capacity = capacity;
	buff->tail = 0;
	buff->head = 0;

	buff->cond_not_full = cond_not_full;
	buff->cond_not_empty= cond_not_empty;
	buff->cond_mutex = cond_mutex;

	buff->data = malloc(capacity * sizeof(Packet_t));
	if (buff->data == NULL){
		return -1;
	}
	return 0;
}


static inline bool queue_is_full(Ringbuffer* buff){
	size_t head = atomic_load_explicit(&buff->head, memory_order_relaxed);
	size_t tail = atomic_load_explicit(&buff->tail, memory_order_acquire);
	return ((head+1) %  buff->capacity) == tail;
}


static inline bool queue_is_empty(Ringbuffer* buff){
	size_t head = atomic_load_explicit(&buff->head, memory_order_acquire);
	size_t tail = atomic_load_explicit(&buff->tail, memory_order_relaxed);
	return head == tail;
}

static inline size_t length(Ringbuffer* buff){
	size_t head = atomic_load_explicit(&buff->head, memory_order_acquire);
	size_t tail = atomic_load_explicit(&buff->tail, memory_order_acquire);
	return (head + buff->capacity - tail) % buff->capacity;
}

static inline bool enqueue(Ringbuffer* buff, Packet_t packet){
	size_t head;
	size_t tail;
	size_t next;

	head = atomic_load_explicit(&buff->head, memory_order_relaxed);
	tail = atomic_load_explicit(&buff->tail, memory_order_acquire);
	next = (head + 1 ) % buff->capacity;
	if (next==tail){ // queue is full
		pthread_mutex_lock(&buff->cond_mutex);
		while(queue_is_full(buff)){
			pthread_cond_wait(&buff->cond_not_full, &buff->cond_mutex);
		}
		pthread_mutex_unlock(&buff->cond_mutex);
	}

	buff->data[head] = packet;
	atomic_store_explicit(&buff->head, next, memory_order_release);
	pthread_cond_signal(&buff->cond_not_empty);
	return true;
}

static inline Packet_t dequeue(Ringbuffer* buff, long long timeout_ns) {
	Packet_t packet;

	assert(timeout_ns>=0);
	struct timespec ts_timout = future_ts(timeout_ns, CLOCK_REALTIME);
	
	size_t head = atomic_load_explicit(&buff->head, memory_order_acquire);
	size_t tail = atomic_load_explicit(&buff->tail, memory_order_relaxed);
	int ret;

	if (head == tail) {
		// Queue is empty: wait
		pthread_mutex_lock(&buff->cond_mutex);
		while (queue_is_empty(buff)) {
			ret = pthread_cond_timedwait(&buff->cond_not_empty, &buff->cond_mutex, &ts_timout);

			if (ret==ETIMEDOUT){
				packet.ts = -2;
				pthread_mutex_unlock(&buff->cond_mutex);
				return packet;
			}
		}
		pthread_mutex_unlock(&buff->cond_mutex);
	}

	packet = buff->data[tail];
	size_t next = (tail + 1) % buff->capacity;
	atomic_store_explicit(&buff->tail, next, memory_order_release);

	pthread_cond_signal(&buff->cond_not_full);
	return packet;
}

typedef enum {
	UDPCOM_EC_OK = 0,
	UDPCOM_EC_SOCK_RECV = 0,
	UDPCOM_EC_SOCK_SEND = 0,
	UDPCOM_EC_POLL_SEND = 0,
	UDPCOM_EC_POLL_RECV= 0,
	UDPCOM_EC_TIMEOUT = 0,
} UDPCOM_EC;

typedef struct {
	PyObject_HEAD
	char * NAME;
	int sock_fd;
	struct sockaddr_in local_addr;
	struct sockaddr_in remote_addr;
	int TIMEOUT;
	int BLOCKING;
	int BIND;
	int CONNECT;
	int DIRECTION;
	volatile atomic_size_t running;
	PacketStats_t stats;
	UDPCOM_EC error;
	pthread_t send_worker;
	pthread_t receive_worker;
	int cpu;
	clockid_t clkid;
	Ringbuffer rec_buff;
	Ringbuffer send_buff;
} UdpCom;

static inline long long nic_timestamp(UdpCom * com){
	struct timespec ts;
	clock_gettime(com->clkid, &ts);
	return ts.tv_sec * 1000000000LL + ts.tv_nsec;
}

static inline long long nic_2_monotonic_ts(UdpCom * com, long long nic_time){
	long long current_nic_time = nic_timestamp(com);
	long long monotonic = now_ns(CLOCK_MONOTONIC);
	long long offset = monotonic - current_nic_time;
	return nic_time + offset;
}

static int UdpCom_init(PyObject *self, PyObject *args, PyObject *kwds) {
	const char *local_ip = NULL;
	int local_port = 0;
	const char *remote_ip = NULL;
	int remote_port = 0;
	int cpu_set = -1;
	int do_bind = 1; // default
	int do_connect = 0; // default
	int capacity = 1024; // default
	long long timeout = 10000000000; // 10s
	//const char* clock_path = "/dev/ptp0"; // TODO: Maybe this could be moved into global scope to save a pointer de-refference??
	const char *name = "UdpCom"; // default
	int direction = 0; // sender

	static char *kwlist[] = {"local_ip", "local_port", "remote_ip", "remote_port", "bind", "connect", "capacity", "name", "direction", "cpu", "timeout", NULL};

	if (!PyArg_ParseTupleAndKeywords(args, kwds, "sisi|$iiisiiL", kwlist,
																	&local_ip, &local_port, &remote_ip, &remote_port, &do_bind, &do_connect, &capacity, &name, &direction, &cpu_set, &timeout)) {
		return -1;  // Signal failure
	}

	/* Typecast generic python object to UdpCom */
	UdpCom *obj = (UdpCom *)self;

	/*
	int fd = open(clock_path, O_RDONLY);
	if (fd < 0) {
		PyErr_SetFromErrno(PyExc_OSError);
		perror("open");
		return -1;
	}

	//Clock ID for nic hardware time-stamps
	obj->clkid = (((unsigned int)~fd) << 3) | 3;

	// test time-stamps are working
	struct timespec ts;
	if (clock_gettime(obj->clkid, &ts) != 0) {
			PyErr_SetFromErrno(PyExc_OSError);
			perror("NIC hardware clock");
			close(fd);
			return -1;
	}

	*/

	/* Data Direction (sender/reciever) */
	if((direction < 0) || (direction > 1)){
		PyErr_SetFromErrno(PyExc_ValueError);
		perror("Unsupported direction");
		return 1;
	}
	obj->DIRECTION = direction;

	/* Generic input arguements */
	obj->TIMEOUT = timeout;
	obj->BIND = do_bind;
	obj->CONNECT = do_connect;
	obj->NAME = strdup(name);
	obj->stats.min_latency_ns = 1000000000LL;
	obj->stats.max_latency_ns = 0;
	obj->cpu = cpu_set;
	obj->sock_fd = -1; // default to error code for un-initialised
	obj->running = false;

	if(buff_init(&obj->send_buff, capacity) < 0){
		PyErr_SetFromErrno(PyExc_OSError);
		return -1;
	}

	if(buff_init(&obj->rec_buff, capacity) <0){
		PyErr_SetFromErrno(PyExc_OSError);
		return -1;
	}

	struct sockaddr_in local_addr = {
		.sin_family = AF_INET,
		.sin_port = htons(local_port),
		.sin_addr.s_addr = inet_addr(local_ip),
	};

	obj->local_addr = local_addr;

	struct sockaddr_in remote_addr = {
		.sin_family = AF_INET,
		.sin_port = htons(remote_port),
		.sin_addr.s_addr = inet_addr(remote_ip),
	};

	obj->remote_addr = remote_addr;

	return 0;  // Success
}


void * send_worker(void * arg){
	UdpCom* obj = (UdpCom*)arg;
	Packet_t next;
	struct timespec time_spec;

	while(obj->running){
		obj->stats.n_send_ticks++;
		next = dequeue(&obj->send_buff, 100000000);
		if (next.ts != -2){ // timeout
			time_spec = ts_from_ns(next.ts); // poll every 1ms
			if (next.ts >= now_ns(CLOCK_MONOTONIC)){
				clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &time_spec, NULL);
			}
			else{
				obj->stats.n_imediate_packets++;
			}
			int ret = sendto(obj->sock_fd, next.data, next.len, 0, (struct sockaddr *)&obj->remote_addr, sizeof(obj->remote_addr));

			assert(ret < 0);
			(void)ret;

			long long send_time_ns = now_ns(CLOCK_MONOTONIC);
			long long latency = send_time_ns - next.ts;
			obj->stats.max_latency_ns = MAX(obj->stats.max_latency_ns, latency);
			obj->stats.min_latency_ns = MIN(obj->stats.min_latency_ns, latency);
			obj->stats.total_latency_ns+=latency;
			obj->stats.n_packets_sent++;
		}
	}
	return NULL;
}

void * receive_worker(void *arg){
	UdpCom* obj = (UdpCom*)arg;
	Packet_t packet;
	struct pollfd pfds;
	pfds.fd = obj->sock_fd;
	pfds.events = POLLIN;
	struct sockaddr src_addr;
	socklen_t addr_size = sizeof(src_addr);


	while(obj->running){
		obj->stats.n_rec_ticks++;
		int ready = poll(&pfds, 1, 10); // 1ms timeout
		assert(ready != -1);
		if (ready==0) { // timout
			continue;	
		}
		else { // ready
			if (pfds.revents & POLLIN) {
				packet.len= recvfrom(pfds.fd, &packet.data, sizeof(packet.data), 0, &src_addr, &addr_size);
				packet.ts = now_ns(CLOCK_MONOTONIC);
				obj->stats.n_packets_rec++;
				assert(packet.len > 0);
				if (queue_is_full(&obj->rec_buff)){
					(void)dequeue(&obj->rec_buff, 0); // drop oldest packet 
					obj->stats.n_rx_packets_dropped++;
				}
				enqueue(&obj->rec_buff, packet);
			} else {                /* POLLERR | POLLHUP */
				assert(close(pfds.fd) == -1);
				return NULL;
			}
		}
	}
	//long long monotinoc_timestamp = nic_2_monotonic_ts(obj, nic_timestamp); // TODO: Move to hardware time-stamps.
	return NULL;
}

static PyObject* start(PyObject *self, PyObject *args) {
	struct sched_param param;
	param.sched_priority = 80;
	int policy = SCHED_FIFO;


	UdpCom *obj = (UdpCom *)self;

	if (obj->running){
    PyErr_SetString(PyExc_ValueError, "Already running.");
		return NULL;
	}

	if (obj->sock_fd <= 0){
    PyErr_SetString(PyExc_OSError, "Socket not initialised.");
		return NULL;
	}
	
	obj->running = true;

	pthread_t * thread;

	void* (*worker)(void*);

	if (obj->DIRECTION == DIR_RECV){
		thread = &obj->receive_worker;
		worker = receive_worker;
	}
	else if(obj->DIRECTION == DIR_SEND){
		thread = &obj->send_worker;
		worker = send_worker;
	}
	else{
		perror("Unsupported direction");
		return PyErr_SetFromErrno(PyExc_ValueError);
	}

	// Create the thread
	if (pthread_create(thread, NULL, worker, (void*)obj) != 0) {
		perror("pthread_create worker");
		return PyErr_SetFromErrno(PyExc_OSError);
	}
	
	if (obj->cpu >= 0){

		// Pin the thread to the selected cpu
    cpu_set_t cpuset;
    CPU_ZERO(&cpuset);
    CPU_SET(obj->cpu, &cpuset);

    // For current thread
    int ret = sched_setaffinity(0, sizeof(cpuset), &cpuset);
    if (ret != 0) {
			perror("sched_setaffinity");
			return PyErr_SetFromErrno(PyExc_OSError);
    }
	}

	if (pthread_setschedparam(*thread, policy, &param) != 0) {
			perror("pthread_setschedparam");
			return PyErr_SetFromErrno(PyExc_OSError);
	}

	Py_RETURN_NONE;
}


static PyObject* stop(PyObject *self, PyObject *args) {

	UdpCom *obj = (UdpCom *)self;

	obj->running = false;
	if (obj->send_worker)
		if(pthread_join(obj->send_worker, NULL)<0)
			return PyErr_SetFromErrno(PyExc_OSError);
	if (obj->receive_worker)
		if(pthread_join(obj->receive_worker, NULL)<0)
			return PyErr_SetFromErrno(PyExc_OSError);
	Py_RETURN_NONE;
}


static PyObject* init_socket(PyObject *self, PyObject *args) {
	UdpCom *obj = (UdpCom *)self;
	int optval = 1;

	if (obj->sock_fd > 0){
    PyErr_SetString(PyExc_OSError, "Socket already open.");
		return NULL;
	}

	obj->sock_fd = socket(AF_INET, SOCK_DGRAM, 0);
	if (obj->sock_fd < 0){
    PyErr_SetString(PyExc_OSError, "Failed to initialise socket.");
		return NULL;
	}
	if (setsockopt(obj->sock_fd, SOL_SOCKET, SO_REUSEADDR, &optval, sizeof(optval)) <0){
    PyErr_SetString(PyExc_OSError, "Failed to configure socket (SO_REUSEADDR).");
		return NULL;
	};
	if(setsockopt(obj->sock_fd, SOL_SOCKET, SO_REUSEPORT, &optval, sizeof(optval)) < 0){
    PyErr_SetString(PyExc_OSError, "Failed to configure socket (SO_REUSEPORT).");
		return NULL;
	};
	if (obj->sock_fd == 0){
    PyErr_SetString(PyExc_OSError, "Cannot use FD0");
    return NULL;
	}

	if (bind(obj->sock_fd, (struct sockaddr *)&obj->local_addr, sizeof(obj->local_addr)) < 0){
    PyErr_SetString(PyExc_OSError, "Failed to Bind");
    return NULL;
	}

	if (obj->DIRECTION == DIR_RECV){
		if(connect(obj->sock_fd, (struct sockaddr *)&obj->remote_addr, sizeof(obj->remote_addr)) < 0){
			PyErr_SetString(PyExc_OSError, "Failed to connect");
			return NULL;
		}
	}

	Py_RETURN_NONE;
}

static PyObject* get_send_length(PyObject *self, PyObject *args) {
	UdpCom *obj = (UdpCom *)self;
	unsigned ret = length(&obj->send_buff);
	return PyLong_FromLongLong(ret);
}

static PyObject* get_receive_length(PyObject *self, PyObject *args) {
	UdpCom *obj = (UdpCom *)self;
	unsigned ret = length(&obj->rec_buff);
	return PyLong_FromLongLong(ret);
}

static PyObject* send_data(PyObject *self, PyObject *args) {
	const char* buf;
	Packet_t packet;

	if (!PyArg_ParseTuple(args, "y#|L", &buf, &packet.len, &packet.ts))
		return NULL;

	assert(packet.len <= sizeof(packet.data));
	if(!memcpy(&packet.data, buf, packet.len))
		return PyErr_SetFromErrno(PyExc_BufferError);

	UdpCom *obj = (UdpCom *)self;
	if (length(&obj->send_buff) >= obj->send_buff.capacity){
		PyErr_SetFromErrno(PyExc_BufferError);
		return NULL;
	}

	if (!enqueue(&obj->send_buff, packet)){
		PyErr_SetFromErrno(PyExc_BlockingIOError);
		return NULL;
	}
	obj->stats.n_packets_req++;
	Py_RETURN_NONE;
}


static PyObject* receive_data(PyObject *self, PyObject *args) {
	long long timeout;
	Packet_t packet;
	if (!PyArg_ParseTuple(args, "L", &timeout))
		return NULL;
	UdpCom *obj = (UdpCom *)self;
	 packet = dequeue(&obj->rec_buff, timeout);
	if (packet.ts == -2){
		PyErr_SetString(PyExc_TimeoutError, "Receive timed out");
		return NULL;
	}
	PyObject *result = Py_BuildValue("y#L", &packet.data, packet.len, packet.ts);
	return result;
}

static PyObject* create_packet_tuple_list(Packet_t packet[], size_t n_packets) {
    PyObject *list = PyList_New(n_packets);
    if (!list) return NULL;

    for (size_t i = 0; i < n_packets; ++i) {
        PyObject *py_data = PyBytes_FromStringAndSize(packet[i].data, packet[i].len);
        PyObject *py_ts   = PyLong_FromLongLong(packet[i].ts);
        if (!py_data || !py_ts) {
            Py_XDECREF(py_data);
            Py_XDECREF(py_ts);
            Py_DECREF(list);
            return NULL;
        }

        PyObject *tuple = PyTuple_New(2);
        if (!tuple) {
            Py_DECREF(py_data);
            Py_DECREF(py_ts);
            Py_DECREF(list);
            return NULL;
        }

        PyTuple_SET_ITEM(tuple, 0, py_data);  // steals reference
        PyTuple_SET_ITEM(tuple, 1, py_ts);    // steals reference

        PyList_SET_ITEM(list, i, tuple);      // steals reference
    }

    return list;
}



static PyObject* UdpCom_receive_batch(PyObject *self, PyObject *args) {
	long long timeout;
	long long n_packets;
	Packet_t* packet_batch;
	bool timed_out = false;
	PyObject* ret = NULL;
	long long n_dropped_start;
	long long n_dropped_during;

	if (!PyArg_ParseTuple(args, "LL", &n_packets, &timeout))
		return NULL;
	UdpCom *obj = (UdpCom *)self;

	packet_batch = malloc(sizeof(Packet_t)*n_packets);
	if(packet_batch==NULL){
		snprintf(buff, sizeof(buff),"Failed to allocated buffer with %lld elements.", n_packets); 
		PyErr_SetString(PyExc_MemoryError, buff);
		return NULL;
	}


	Py_BEGIN_ALLOW_THREADS
	n_dropped_start = obj->stats.n_rx_packets_dropped;
	for (int i = 0; i<n_packets; i++){
		packet_batch[i] = dequeue(&obj->rec_buff, timeout);
		if (packet_batch[i].ts == -2){
			timed_out = true;
			break;

		}
	}
	n_dropped_during = obj->stats.n_rx_packets_dropped-n_dropped_start;
	Py_END_ALLOW_THREADS


	if (timed_out){
		PyErr_SetString(PyExc_TimeoutError, "Timed out waiting for data");
		ret=NULL;
	}
	else if (n_dropped_during!=0) {
		snprintf(buff, sizeof(buff), "Missed %lld packets",n_dropped_during) ;
		PyErr_SetString(PyExc_ValueError, buff);
		ret=NULL;
	}
	else{
		ret = create_packet_tuple_list(packet_batch, n_packets);
	}

	free(packet_batch);
	return ret;
}


static PyObject* close_socket(PyObject *self, PyObject *args) {
	UdpCom *obj = (UdpCom *)self;
	if (obj->sock_fd >= 0) close(obj->sock_fd);
	obj->sock_fd = -1;
	Py_RETURN_NONE;
}

static void UdpCom_dealoc(PyObject *self) {
	UdpCom *obj = (UdpCom*)self;
	if (obj->sock_fd > 0)
		close(obj->sock_fd);
	if (obj->NAME)
		free(obj->NAME);

	Py_TYPE(self)->tp_free(self);
}

#define ADD_LONG(dict, key, val)                \
    do {                                        \
        PyObject *_v = PyLong_FromLong(val);    \
        if (_v) {                               \
            PyDict_SetItemString(dict, key, _v);\
            Py_DECREF(_v);                      \
        }                                       \
    } while (0)

static PyObject* get_packet_stats(PyObject *self, PyObject *args) {
	PyObject *dict = PyDict_New();  // create a new empty dict
	if (!dict) return NULL;
	//
	UdpCom *obj = (UdpCom*)self;
	// Create some values (e.g., ints, floats)
	ADD_LONG(dict, "n_packets_rec", obj->stats.n_packets_rec);
	ADD_LONG(dict, "n_packets_req", obj->stats.n_packets_req);
	ADD_LONG(dict, "n_packets_sent", obj->stats.n_packets_sent);
	ADD_LONG(dict, "n_rx_packets_dropped", obj->stats.n_rx_packets_dropped);
	ADD_LONG(dict, "min_latency_ns", obj->stats.min_latency_ns);
	ADD_LONG(dict, "max_latency_ns", obj->stats.max_latency_ns);
	ADD_LONG(dict, "total_latency_ns", obj->stats.total_latency_ns);
	ADD_LONG(dict, "n_send_ticks", obj->stats.n_send_ticks);
	ADD_LONG(dict, "n_rec_ticks", obj->stats.n_rec_ticks);
	ADD_LONG(dict, "n_imediate_packets", obj->stats.n_imediate_packets);

	return dict;  // return the dictionary
}

static PyObject* UdpCom_repr(PyObject* self) {
	UdpCom *obj = (UdpCom*)self;
	char ip_str[INET_ADDRSTRLEN];
	char *direction_str;

	// Convert IP to string
	const char* result = inet_ntop(AF_INET, &obj->remote_addr.sin_addr, ip_str, sizeof(ip_str));
	if (!result) {
		PyErr_SetString(PyExc_RuntimeError, "Failed to convert IP address");
		return NULL;
	}
	// Convert port from network to host byte order
	int port = ntohs(obj->remote_addr.sin_port);

	if (obj->DIRECTION == DIR_RECV){
		direction_str="<-";
	}
	else{
		direction_str="->";
	}


	// Format string to return to Python
	return PyUnicode_FromFormat("UdpCom[%d]%s(%s:%d)", obj->sock_fd, direction_str, ip_str, port);
}


static PyObject* UdpCom_is_running(PyObject *self, PyObject *args) {
	UdpCom *obj = (UdpCom*)self;
	
	if (obj->running)
		Py_RETURN_TRUE;
	else
		Py_RETURN_FALSE;
}

static PyObject* UdpCom_purge(PyObject *self, PyObject *args) {
	UdpCom *obj = (UdpCom*)self;

	if (stop(self, NULL) == NULL){
		return NULL;
	}

	obj->rec_buff.head = 0;
	obj->rec_buff.tail = 0;
	obj->send_buff.head = 0;
	obj->send_buff.tail = 0;

	if (start(self, NULL) == NULL){
		return NULL;
	}

	Py_RETURN_NONE;
}


static inline Py_hash_t UdpCom_hash(PyObject *self) {

	UdpCom *obj = (UdpCom*)self;
	uint32_t local_ip    = obj->local_addr.sin_addr.s_addr;
	uint16_t local_port  = ntohs(obj->local_addr.sin_port);
	uint32_t remote_ip   = obj->remote_addr.sin_addr.s_addr;
	uint16_t remote_port = ntohs(obj->remote_addr.sin_port);

	uint64_t h = 2166136261u;  // FNV-1a offset basis
	h = (h ^ (uint64_t)obj->DIRECTION) * 16777619;
	h = (h ^ local_ip)         * 16777619;
	h = (h ^ local_port)       * 16777619;
	h = (h ^ remote_ip)        * 16777619;
	h = (h ^ remote_port)      * 16777619;

	// Truncate or cast to Py_hash_t (usually a signed long)
	if (h == (uint64_t)-1) {
		return (Py_hash_t)-2;
	} else {
		return (Py_hash_t)h;
	}
}

static PyMethodDef UdpCom_methods[] = {
    {"send_data", 		send_data, 		METH_VARARGS, "Send data over UDP"},
    {"receive_data", 	receive_data, METH_VARARGS, "Recieve data over UDP"},
    {"receive_batch", 	UdpCom_receive_batch, METH_VARARGS, "Recieve batch of data over UDP"},
    {"init_socket", 	init_socket, 	METH_NOARGS, "Initialise UDP socket."},
    {"close_socket", 	close_socket, METH_NOARGS, "Close UDP socket."},
    {"start", 				start, 				METH_NOARGS, "start send/recieve workers."},
    {"stop", 					stop, 					METH_NOARGS, "end send/recieve workers."},
    {"get_packet_stats", 	get_packet_stats, METH_NOARGS, "Send data over UDP"},
    {"get_send_length", 	get_send_length, METH_NOARGS, "Get number of packets in send queue."},
    {"get_receive_length", 	get_receive_length, METH_NOARGS, "Get number of packets in recieve queue."},
    {"is_running", UdpCom_is_running, METH_NOARGS, "Return True if the comm object is currenently running."},
    {"purge", UdpCom_purge, METH_NOARGS, "Clear buffers."},

    {NULL}  // Sentinel
};

static PyTypeObject UDPSocketType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "udpcom.UdpCom",
    .tp_basicsize = sizeof(UdpCom),
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
    .tp_doc = "Custom UDP Socket type",
    .tp_methods = UdpCom_methods,
    .tp_new = PyType_GenericNew,
		.tp_init = UdpCom_init,
		.tp_dealloc = UdpCom_dealoc,
    .tp_hash = UdpCom_hash,  // <-- add this line
		.tp_repr = UdpCom_repr,
};

//static PyMethodDef UDPCommMethods[] = {
//	{"init_socket", init_socket, METH_VARARGS, "Initialize the UDP socket"},
//	{"send_data", send_data, METH_VARARGS, "Send data and return timestamp"},
//	{"receive_data", receive_data, METH_VARARGS, "Receive data and timestamp"},
//	{"close_socket", close_socket, METH_NOARGS, "Close the socket"},
//	{NULL, NULL, 0, NULL}
//};

static struct PyModuleDef udpcommodule = {
	PyModuleDef_HEAD_INIT,
	"udpcom",
	NULL,
	-1,
	NULL
};

PyMODINIT_FUNC PyInit_udpcom(void) {
    PyObject *m;
    if (PyType_Ready(&UDPSocketType) < 0)
        return NULL;

    m = PyModule_Create(&udpcommodule);
    if (!m) return NULL;

    Py_INCREF(&UDPSocketType);
    PyModule_AddObject(m, "UdpCom", (PyObject *)&UDPSocketType);
    return m;
}
